#!/usr/bin/env python3
"""
=============================================================
  SOKOBAN — Terminal Edition
=============================================================
  Level Flat-String Format:  <width>:<row0><row1>...<rowN>
  Each row is exactly <width> characters.  Spaces ARE tiles.

  Tile legend
  -----------
    #   Wall              @   Pusher
    +   Pusher on Goal    $   Box
    *   Box on Goal       .   Goal (empty)
        (space = empty floor)

  Controls
  --------
    W / ↑   move up        S / ↓   move down
    A / ←   move left      D / →   move right
    R       restart level   Q       quit
=============================================================
"""

import os
import sys

# ─── Platform: single keypress (no Enter needed) ─────────────────────────────

try:
    import tty, termios
    _UNIX = True
except ImportError:
    import msvcrt  # type: ignore
    _UNIX = False


def getch() -> str:
    """Return one normalised key: 'w','a','s','d','r','q', or ''."""
    if _UNIX:
        fd  = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.buffer.read(1)
            if ch == b'\x1b':           # possible arrow-key escape sequence
                nxt = sys.stdin.buffer.read(1)
                if nxt == b'[':
                    arrow = sys.stdin.buffer.read(1)
                    return {b'A': 'w', b'B': 's',
                            b'C': 'd', b'D': 'a'}.get(arrow, '')
                return ''
            return ch.decode('utf-8', errors='ignore')
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    else:
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):    # Windows special / extended key
            arrow = msvcrt.getch()
            return {b'H': 'w', b'P': 's',
                    b'M': 'd', b'K': 'a'}.get(arrow, '')
        return ch.decode('utf-8', errors='ignore')


# ─── Level loading ────────────────────────────────────────────────────────────

def load_level(flat: str):
    """
    Parse a flat-string level  ->  (board, width, height)

    board  : list[list[str]]   mutable 2-D grid of single characters
    width  : int
    height : int

    Example
    -------
    "6:#######@ $.#######"
      -> width = 6
      -> data  = "#######@ $.#######"
      -> rows  = ["######", "#@ $.#", "######"]
    """
    colon  = flat.index(':')
    width  = int(flat[:colon])
    data   = flat[colon + 1:]

    # Pad data to a complete last row if the string is short
    remainder = len(data) % width
    if remainder:
        data += ' ' * (width - remainder)

    height = len(data) // width
    board  = [list(data[r * width:(r + 1) * width]) for r in range(height)]
    return board, width, height


# ─── ANSI colour map ──────────────────────────────────────────────────────────

_COLOUR = {
    '#': '\033[90m#\033[0m',    # dark grey  — wall
    '@': '\033[92m@\033[0m',    # green      — pusher
    '+': '\033[96m+\033[0m',    # cyan       — pusher on goal
    '$': '\033[93m$\033[0m',    # yellow     — box
    '*': '\033[95m*\033[0m',    # magenta    — box on goal (solved tile)
    '.': '\033[94m.\033[0m',    # blue       — empty goal
    ' ': ' ',
}


def _clear():
    os.system('cls' if os.name == 'nt' else 'clear')


def _count_boxes(board):
    total   = sum(row.count('$') + row.count('*') for row in board)
    on_goal = sum(row.count('*')                   for row in board)
    return total, on_goal


def render(board, width: int, moves: int, name: str = ''):
    _clear()
    total, on_goal = _count_boxes(board)

    bar   = '─' * (width + 4)
    label = f' SOKOBAN  {name}'
    pad   = max(0, width + 4 - len(label) - 1)
    print(f"\033[1m┌{bar}┐\033[0m")
    print(f"\033[1m│{label}{' ' * pad}│\033[0m")
    print(f"\033[1m└{bar}┘\033[0m\n")

    for row in board:
        print('  ' + ''.join(_COLOUR.get(c, c) for c in row))

    print(f'\n  \033[90mMoves:\033[0m \033[1m{moves:4d}\033[0m'
          f'   \033[90mBoxes on goal:\033[0m \033[1m{on_goal}/{total}\033[0m')
    print('\n  \033[90mW/A/S/D  ↑←↓→  move  │  R  restart  │  Q  quit\033[0m\n')


# ─── Sokoban physics ─────────────────────────────────────────────────────────

_BOXES = frozenset(('$', '*'))
_WALLS = frozenset(('#',))


def _find_pusher(board):
    for r, row in enumerate(board):
        for c, cell in enumerate(row):
            if cell in ('@', '+'):
                return r, c
    raise RuntimeError('No pusher (@/+) found in level!')


def _set_tile(board, r: int, c: int, entity, is_goal: bool):
    """
    Write the correct composite character at (r, c).

    entity  : '@' (pusher)  |  '$' (box)  |  None (just clear)
    is_goal : whether this square is a goal square
    """
    if entity == '@':
        board[r][c] = '+' if is_goal else '@'
    elif entity == '$':
        board[r][c] = '*' if is_goal else '$'
    else:                           # clearing — entity has left this square
        board[r][c] = '.' if is_goal else ' '


def move(board, dr: int, dc: int) -> bool:
    """
    Attempt to move the pusher by (dr, dc).

    Physics rules enforced:
      - Cannot walk through walls.
      - Can push a box only if the square behind it is empty or a bare goal.
      - Cannot push two boxes at once.
      - Cannot push a box into a wall.
      - Goal squares are remembered: moving onto a goal gives '@' -> '+',
        moving off a goal restores '.'; same for boxes ('$' / '*').

    Returns True iff the board changed.
    """
    rows, cols = len(board), len(board[0])
    pr, pc     = _find_pusher(board)
    nr, nc     = pr + dr, pc + dc       # pusher destination

    if not (0 <= nr < rows and 0 <= nc < cols):
        return False

    target = board[nr][nc]

    if target in _WALLS:
        return False

    pusher_was_on_goal = (board[pr][pc] == '+')

    if target in _BOXES:
        # ── Push a box ────────────────────────────────────────────────────
        bnr, bnc = nr + dr, nc + dc     # where box would land

        if not (0 <= bnr < rows and 0 <= bnc < cols):
            return False
        behind = board[bnr][bnc]
        if behind in _WALLS or behind in _BOXES:
            return False                # blocked

        box_was_on_goal   = (target == '*')
        box_lands_on_goal = (behind == '.')

        _set_tile(board, bnr, bnc, '$', box_lands_on_goal)   # box new pos
        _set_tile(board, nr,  nc,  '@', box_was_on_goal)     # pusher new pos

    else:
        # ── Walk into empty floor or goal ─────────────────────────────────
        _set_tile(board, nr, nc, '@', target == '.')

    # Clear pusher's old square (restoring goal dot if needed)
    _set_tile(board, pr, pc, None, pusher_was_on_goal)
    return True


def check_win(board) -> bool:
    """Win when no bare box ($) remains — all boxes are on goals (*)."""
    return all(cell != '$' for row in board for cell in row)


# ─── Built-in levels ─────────────────────────────────────────────────────────
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  FLAT-STRING FORMAT  —  derivation for each level                       │
# │                                                                         │
# │  Format:  "<width>:<row0><row1>...<rowN>"                               │
# │  • The integer before ':' is the number of columns.                     │
# │  • Every character after ':' is a tile, left→right, top→bottom.        │
# │  • Space characters ARE meaningful (empty floor).                       │
# │  • The string length after ':' must be a multiple of <width>.           │
# └─────────────────────────────────────────────────────────────────────────┘
#
# ── Level 1 derivation ────────────────────────────────────────────────────
#
#   Visual grid (width = 6):
#
#     Col:  0 1 2 3 4 5
#     Row0: # # # # # #
#     Row1: # @ _ $ . #     (_ = space / empty floor)
#     Row2: # # # # # #
#
#   Rows as strings (6 chars each):
#     Row0 = "######"
#     Row1 = "#@ $.#"
#     Row2 = "######"
#
#   Flat string = "6:" + "######" + "#@ $.#" + "######"
#               = "6:#######@ $.#######"             ← Example 1
#
# ── Level 2 derivation ────────────────────────────────────────────────────
#
#   Visual grid (width = 8):
#
#     Col:  0 1 2 3 4 5 6 7
#     Row0: # # # # # # # #
#     Row1: # _ _ _ _ _ _ #
#     Row2: # _ . $ @ _ _ #     goal@col2, box@col3, pusher@col4
#     Row3: # _ _ $ _ _ _ #     box@col3
#     Row4: # # _ . _ _ _ #     goal@col3
#     Row5: # # # # # # # #
#
#   Rows as strings (8 chars each):
#     Row0 = "########"
#     Row1 = "#      #"
#     Row2 = "# .$@  #"
#     Row3 = "#  $   #"
#     Row4 = "## .   #"
#     Row5 = "########"
#
#   Flat string = "8:" + "########" + "#      #" + "# .$@  #"
#                      + "#  $   #" + "## .   #" + "########"
#               = "8:########  #      ## .$@  ##  $   ### .   ########"
#                                                                  ← Example 2
#
#   Quick solution (2 moves):
#     1. Move LEFT  → pusher pushes box@(2,3) to (2,2)=goal  → box becomes *
#     2. Move DOWN  → pusher pushes box@(3,3) to (4,3)=goal  → box becomes *
#     → Level Clear!

LEVELS: dict = {

    # ─ Level 1: Tutorial — 1 box, 1 goal (width=6) ────────────────────────
    # ######
    # #@ $.#
    # ######
    '1 — Tutorial':
        '6:'
        '######'
        '#@ $.#'
        '######',

    # ─ Level 2: Classic — 2 boxes, 2 goals (width=8) ──────────────────────
    # ########
    # #      #
    # # .$@  #   goal@(2,2), box@(2,3), pusher@(2,4)
    # #  $   #   box@(3,3)
    # ## .   #   goal@(4,3)  ← wall at cols 0-1 to restrict space
    # ########
    '2 — Classic':
        '8:'
        '########'
        '#      #'
        '# .$@  #'
        '#  $   #'
        '## .   #'
        '########',

    # ─ Level 3: Intermediate — 3 boxes, 3 goals (width=10) ────────────────
    # ##########
    # #@       #
    # #  $ $ $ #
    # ## ##    #
    # #  ##... #
    # ##########
    '3 — Intermediate':
        '10:'
        '##########'
        '#@       #'
        '#  $ $ $ #'
        '## ##    #'
        '#  ##... #'
        '##########',

    # ─ Level 4: Challenge — 4 boxes, 4 goals (width=10) ───────────────────
    # ##########
    # # @     #
    # # $$ $  #
    # #    $  #
    # ## .... #
    # ##########
    '4 — Challenge':
        '10:'
        '##########'
        '# @      #'
        '# $$ $   #'
        '#    $   #'
        '## ....  #'
        '##########',
}


# ─── Game loop ────────────────────────────────────────────────────────────────

def play(flat_original: str, name: str = '') -> str:
    """Run one level. Returns 'win', 'quit', or 'menu'."""
    board, width, _ = load_level(flat_original)
    moves = 0
    render(board, width, moves, name)

    while True:
        key = getch().lower()

        if key == 'q':
            _clear()
            print('\n  Goodbye! 👋\n')
            return 'quit'

        if key == 'r':
            board, width, _ = load_level(flat_original)
            moves = 0
            render(board, width, moves, name)
            continue

        direction = {'w': (-1, 0), 's': (1, 0),
                     'a': (0, -1), 'd': (0, 1)}.get(key)
        if direction is None:
            continue

        if move(board, *direction):
            moves += 1

        render(board, width, moves, name)

        if check_win(board):
            print(f'  \033[1;92m🎉  Level Clear!'
                  f'  Solved in {moves} moves.  🎉\033[0m\n')
            input('  Press Enter to return to menu… ')
            return 'win'


# ─── Menu ─────────────────────────────────────────────────────────────────────

def level_menu():
    """Show level select; return (flat_string, name) or None to quit."""
    _clear()
    print('\033[1m')
    print('  ╔════════════════════════════════╗')
    print('  ║    S  O  K  O  B  A  N        ║')
    print('  ╚════════════════════════════════╝')
    print('\033[0m')

    keys = list(LEVELS.keys())
    for i, name in enumerate(keys, 1):
        print(f'  [{i}]  {name}')
    print()
    print('  [C]  Load custom flat-string level')
    print('  [Q]  Quit')
    print()

    while True:
        raw = input('  Your choice: ').strip().lower()

        if raw == 'q':
            return None

        if raw == 'c':
            print()
            flat = input('  Paste flat-string level: ').strip()
            if flat:
                return flat, 'Custom'
            print('  (empty — try again)\n')
            continue

        try:
            idx = int(raw) - 1
            if 0 <= idx < len(keys):
                k = keys[idx]
                return LEVELS[k], k
        except ValueError:
            pass

        print('  \033[91mInvalid choice — try again.\033[0m\n')


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    while True:
        choice = level_menu()
        if choice is None:
            _clear()
            print('\n  Thanks for playing Sokoban! 👋\n')
            break
        flat, name = choice
        if play(flat, name) == 'quit':
            break


if __name__ == '__main__':
    main()