import os, time

# Load level
def load_level(flat):
    colon  = flat.index(':')
    width  = int(flat[:colon])
    data   = flat[colon + 1:]

    static, player, boxes, goals = [], None, set(), set()

    for i in range(0, len(data), width):
        r   = len(static)
        row = list(data[i : i + width].ljust(width))
        static_row = []
        for c, ch in enumerate(row):
            if   ch == '#':  static_row.append('#')
            elif ch == '.':  static_row.append('.')  ; goals.add((r,c))
            elif ch == '@':  player=(r,c)            ; static_row.append(' ')
            elif ch == '+':  player=(r,c)            ; static_row.append('.'); goals.add((r,c))
            elif ch == '$':  boxes.add((r,c))        ; static_row.append(' ')
            elif ch == '*':  boxes.add((r,c))        ; static_row.append('.'); goals.add((r,c))
            else:            static_row.append(' ')
        static.append(static_row)

    return static, player, frozenset(boxes), frozenset(goals)

# Render
def render(static, player, boxes, goals):
    os.system('cls' if os.name == 'nt' else 'clear')
    for r, row in enumerate(static):
        line = ''
        for c, tile in enumerate(row):
            pos     = (r, c)
            on_goal = (tile == '.')
            if   pos == player and on_goal: line += '+'
            elif pos == player:             line += '@'
            elif pos in boxes  and on_goal: line += '*'
            elif pos in boxes:              line += '$'
            else:                           line += tile
        print(line)

# Heuristic  h(state)
def heuristic(boxes, goals):
    """Manhattan distance = |row_a - row_b| + |col_a - col_b|"""
    total = 0
    for (br, bc) in boxes:
        nearest = min(abs(br - gr) + abs(bc - gc) for (gr, gc) in goals)
        total += nearest
    return total

# Deadlock check
def is_deadlocked(static, boxes, goals):
    rows, cols = len(static), len(static[0])
    for (r, c) in boxes:
        if (r, c) in goals:
            continue
        def wall(dr, dc):
            nr, nc = r+dr, c+dc
            return not(0<=nr<rows and 0<=nc<cols) or static[nr][nc]=='#'
        if (wall(-1,0) or wall(1,0)) and (wall(0,-1) or wall(0,1)):
            return True
    return False


# A* Solving
MOVES = {'L':(0,-1), 'U':(-1,0), 'R':(0,1), 'D':(1,0)}

def solve(static, start_player, start_boxes, goals):
    """
    A* with a plain list instead of a heap.

    open_list  — states we still need to explore
                 each entry is  [f, g, player, boxes, path]
    visited    — states we have already fully explored (set)

    Every loop we do all this:
      1. Find the entry in open_list with the smallest f  (best guess)
      2. Remove it and mark it visited
      3. Try all 4 moves; for each valid move, compute new f and add to list
      4. If the new state is the win state, return the path immediately
    """
    rows, cols = len(static), len(static[0])

    # Starting entry: [f, g, player, boxes, path]
    start_f = heuristic(start_boxes, goals)
    open_list = [[start_f, 0, start_player, start_boxes, ""]]
    visited   = set()

    while open_list:

        # Step 1: pick the entry with the lowest f 
        best_index = 0
        for i in range(1, len(open_list)):
            if open_list[i][0] < open_list[best_index][0]:
                best_index = i

        #  Step 2: remove it from the list
        f, g, player, boxes, path = open_list.pop(best_index)

        state = (player, boxes)
        if state in visited:
            continue
        visited.add(state)

        #  Step 3: try every direction 
        pr, pc = player
        for letter, (dr, dc) in MOVES.items():
            nr, nc = pr+dr, pc+dc

            if not(0<=nr<rows and 0<=nc<cols) or static[nr][nc]=='#':
                continue

            new_boxes = set(boxes)

            # Pushing a box?
            if (nr, nc) in boxes:
                br, bc = nr+dr, nc+dc
                if not(0<=br<rows and 0<=bc<cols):    continue
                if static[br][bc]=='#':               continue
                if (br, bc) in boxes:                 continue
                new_boxes.discard((nr, nc))
                new_boxes.add((br, bc))

            frozen = frozenset(new_boxes)

            if is_deadlocked(static, frozen, goals):
                continue

            new_path = path + letter

            # Step 4: win check 
            if frozen == goals:
                return new_path

            new_g = g + 1
            new_f = new_g + heuristic(frozen, goals)
            open_list.append([new_f, new_g, (nr, nc), frozen, new_path])

    return None   

# Playback
def apply_move(static, player, boxes, dr, dc):
    rows, cols = len(static), len(static[0])
    pr, pc = player
    nr, nc = pr+dr, pc+dc
    if not(0<=nr<rows and 0<=nc<cols) or static[nr][nc]=='#':
        return player, boxes
    new_boxes = set(boxes)
    if (nr, nc) in boxes:
        br, bc = nr+dr, nc+dc
        if not(0<=br<rows and 0<=bc<cols): return player, boxes
        if static[br][bc]=='#' or (br,bc) in boxes: return player, boxes
        new_boxes.discard((nr, nc))
        new_boxes.add((br, bc))
    return (nr, nc), frozenset(new_boxes)

def playback(static, start_player, start_boxes, goals, lurd, delay=0.35):
    print(f"\n  Solution : {lurd}")
    print(f"  Moves    : {len(lurd)}")
    print("\n  Playback starts in 2 s …")
    time.sleep(2)

    player, boxes = start_player, start_boxes
    render(static, player, boxes, goals)
    time.sleep(delay)

    for i, letter in enumerate(lurd):
        dr, dc = MOVES[letter]
        player, boxes = apply_move(static, player, boxes, dr, dc)
        render(static, player, boxes, goals)
        print(f"\n  Step {i+1:>3}/{len(lurd)}   move={letter}   path: {lurd[:i+1]}")
        time.sleep(delay)

    print("\n  Level Clear!\n")


# Main
LEVELS = {
    "1": ("Level 1 — Tutorial",       "6:#######@ $.#######"),
    "2": ("Level 2 — Classic 8-wide", "8:  #####   #   #   #$  ####  $.##    $ .#### #@ #  # .  #  ######"),
    "3": ("Level 3 — Mini hard",      "7:  #####  #.  ## #$ $## @.  ###  #####"),
}

def main():
    print("                              ")
    print("     SOKOBAN  SOLVER          ")
    print("")
    for k, (name, _) in LEVELS.items():
        print(f"  {k}. {name:<27}")
    print("                              ")

    choice = input("\nChoose level (1/2/3) or paste flat string: ").strip()
    if choice in LEVELS:
        name, flat = LEVELS[choice]
    elif ':' in choice:
        name, flat = "Custom", choice
    else:
        name, flat = LEVELS["1"]

    print(f"\n  Loading : {name}")
    static, player, boxes, goals = load_level(flat)

    print("  Initial board:")
    render(static, player, boxes, goals)

    print("\n  Running  … ", end='', flush=True)
    t0   = time.time()
    lurd = solve(static, player, boxes, goals)
    print(f"done in {time.time()-t0:.3f}s")

    if lurd is None:
        print("  No solution found.")
        return

    playback(static, player, boxes, goals, lurd, delay=0.35)

if __name__ == '__main__':
    main()