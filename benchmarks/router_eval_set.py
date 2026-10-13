"""
Held-out routing evaluation set, version 1. Written BEFORE the router existed; the router is developed against the older 30-task
probe set (benchmarks/router_probe.py) and this set is run once. Its SHA-256 is recorded with every result, so a label edited
after a run shows up as a different hash.

Each case:  id, category, task, page_path, execution, perception, ambiguous, value
  page_path   what browser_observe would already have reported (None = the router runs at task start, before any observation):
              semantic | table | visual | mixed
  execution   "typed"   the existing typed tools are the right way (including one structured operation that returns a lot)
              "program" many predictable operations, or deterministic computation, where a program saves model round trips
  perception  what the task needs to be looked at with: "semantic" (DOM, text, elements), "structured" (complete table or record
              extraction), "visual" (screenshots). A task can need several. Perception is independent of execution.
  ambiguous   the request cannot be classified from its words; the right behaviour is to flag it, not to guess confidently
  value       what is known about routing it correctly:
              "measured_program_needed"  the typed tools failed this kind of task in our rocket runs (1 of 9 against 9 of 9)
              "measured_typed_better"    typed tools passed it in our runs, and a script agent was not faster (chess, draw, shop, table)
              "hypothesis_program_helps" plausible, not measured here
              "typed_expected"           ordinary work, no evidence a program helps
              "unknown"                  ambiguous
"""

import hashlib
import json

S, T, V = "semantic", "structured", "visual"

# (category, task, page_path, execution, perception, ambiguous, value)
_CASES = [
    # ordinary navigation, search and form interaction
    ("ordinary", "Go to Wikipedia and find out when the Eiffel Tower was completed", None, "typed", [S], False, "typed_expected"),
    ("ordinary", "Search for a vegetarian lasagna recipe and read me the ingredient list", None, "typed", [S], False, "typed_expected"),
    ("ordinary", "Open the BBC homepage and tell me the top headline", "semantic", "typed", [S], False, "typed_expected"),
    ("ordinary", "Log in with the saved credentials and open my orders page", "semantic", "typed", [S], False, "typed_expected"),
    ("ordinary", "Put my email in the newsletter signup box and press subscribe", "semantic", "typed", [S], False, "typed_expected"),
    ("ordinary", "Find the opening hours of the nearest pharmacy on Google Maps", None, "typed", [S], False, "typed_expected"),
    ("ordinary", "Compare the price of the iPhone 16 on Amazon and on Flipkart", None, "typed", [S], False, "typed_expected"),
    ("ordinary", "Open the pricing page and tell me what the Pro plan costs", "semantic", "typed", [S], False, "typed_expected"),
    ("ordinary", "Book the earliest available slot on the clinic's appointment page", "semantic", "typed", [S], False, "typed_expected"),
    ("ordinary", "Go back to the previous page and click the second link", "semantic", "typed", [S], False, "typed_expected"),
    # a few repetitive operations, below the point where a program pays off
    ("few_repetitive", "Add these three books to the cart: Dune, Emma and Ulysses", "semantic", "typed", [S], False, "measured_typed_better"),
    ("few_repetitive", "Tick the boxes for Monday, Wednesday and Friday and then save", "semantic", "typed", [S], False, "typed_expected"),
    ("few_repetitive", "Open the first four search results in separate tabs and report their titles", "semantic", "typed", [S], False, "typed_expected"),
    ("few_repetitive", "Fill the five fields of the shipping address form with this address", "semantic", "typed", [S], False, "typed_expected"),
    ("few_repetitive", "Upvote the top three comments", "semantic", "typed", [S], False, "typed_expected"),
    ("few_repetitive", "Select size M, colour blue and quantity 2, then add it to the cart", "semantic", "typed", [S], False, "measured_typed_better"),
    ("few_repetitive", "Change the language, the currency and the timezone in the settings page", "semantic", "typed", [S], False, "typed_expected"),
    ("few_repetitive", "Click each of the six tabs on this page and read out their headings", "semantic", "typed", [S], False, "typed_expected"),
    # chess, Wordle and Excalidraw with a handful of actions: look at it, but no long sequence
    ("game_few_actions", "Play e2 to e4 as White's opening move", "visual", "typed", [S, V], False, "measured_typed_better"),
    ("game_few_actions", "It is White's move in this chess position: play the best capture", "visual", "typed", [S, V], False, "measured_typed_better"),
    ("game_few_actions", "Make the next Wordle guess from the feedback shown so far", "visual", "typed", [S, V], False, "measured_typed_better"),
    ("game_few_actions", "Draw a single arrow from the box to the circle on the whiteboard", "visual", "typed", [S, V], False, "measured_typed_better"),
    ("game_few_actions", "Draw one red rectangle on the Excalidraw canvas", "visual", "typed", [S, V], False, "measured_typed_better"),
    ("game_few_actions", "Click the highlighted cell in this minesweeper grid", "visual", "typed", [S, V], False, "typed_expected"),
    ("game_few_actions", "Move the pawn on d2 forward two squares", "visual", "typed", [S, V], False, "measured_typed_better"),
    ("game_few_actions", "Add a text label that says Start next to the first shape", "visual", "typed", [S, V], False, "typed_expected"),
    # long deterministic drawing
    ("long_drawing", "Draw a detailed sailing ship on the sea with three sails, waves, a sun and ten clouds in Excalidraw", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a full chessboard with all 64 squares coloured and the pieces in their starting positions on the whiteboard", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a floor plan of a three bedroom house with doors, windows and furniture labels", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a solar system diagram with the sun, eight planets and their orbits", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a detailed city skyline with 25 buildings, lit windows and a moon", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a mind map with one central idea and 20 connected branches", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a 10 by 10 grid and colour in the cells so they spell the letter H", "visual", "program", [S, V], False, "measured_program_needed"),
    ("long_drawing", "Draw a flowchart with 15 boxes joined by arrows for a login process", "visual", "program", [S, V], False, "measured_program_needed"),
    # complete structured table extraction: one structured operation, however many rows
    ("table_extraction", "Extract all 57 rows of the grade history table", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "Copy every row of the attendance table into a list, including the other pages", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "List all employees with their department and salary from the directory table", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "Get the whole price table, every page of it", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "Read the full standings table and tell me who is in 7th place", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "Export all 200 rows of this results table as text", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "Collect the complete fixtures table, all pages", "table", "typed", [T, S], False, "measured_typed_better"),
    ("table_extraction", "List every course with its credits and grade from the transcript table", "table", "typed", [T, S], False, "measured_typed_better"),
    # needs to be looked at, no long sequence of actions
    ("visual_only", "Look at this bar chart and tell me which month had the highest sales", "visual", "typed", [V], False, "typed_expected"),
    ("visual_only", "What does the logo in the top left corner look like?", "visual", "typed", [V], False, "typed_expected"),
    ("visual_only", "Describe the layout of this dashboard and say what the red marker means", "visual", "typed", [V, S], False, "typed_expected"),
    ("visual_only", "Which of the pictures on this page shows a dog?", "visual", "typed", [V], False, "typed_expected"),
    ("visual_only", "Read the number shown on the gauge", "visual", "typed", [V], False, "typed_expected"),
    ("visual_only", "Check whether the map pin is inside the shaded region", "visual", "typed", [V], False, "typed_expected"),
    # many predictable operations on ordinary DOM pages: a program helps, screenshots are unnecessary
    ("bulk_dom", "Enter these 45 customer records into the CRM form, one after another", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Go through all 50 pages of search results and collect each product title", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Tick the box next to each of the 80 emails in this list and archive them", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Fill in the 30 line items of this purchase order from the values below", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Set the price of each of the 36 products in the admin panel to the new values I give you", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Open every one of the 25 profile links and note the job title on each", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Rename the 40 tags following the pattern tag-01 to tag-40", "semantic", "program", [S], False, "hypothesis_program_helps"),
    ("bulk_dom", "Click Accept on each of the 22 pending requests", "semantic", "program", [S], False, "hypothesis_program_helps"),
    # cannot be classified from the words: the right behaviour is to flag, not to guess with confidence
    ("ambiguous", "Make the drawing look nicer", "visual", "typed", [S, V], True, "unknown"),
    ("ambiguous", "Fill out the form", "semantic", "typed", [S], True, "unknown"),
    ("ambiguous", "Clean up this page", "semantic", "typed", [S], True, "unknown"),
    ("ambiguous", "Do the same thing for the rest of them", None, "typed", [S], True, "unknown"),
    ("ambiguous", "Handle the pending items", None, "typed", [S], True, "unknown"),
    ("ambiguous", "Organise this board", "semantic", "typed", [S], True, "unknown"),
    ("ambiguous", "Finish the order", None, "typed", [S], True, "unknown"),
    ("ambiguous", "Update the records", None, "typed", [S], True, "unknown"),
    # research (handled by the multi-agent path, not by programs)
    ("research", "Find five recent papers on retrieval augmented generation with links", None, "typed", [S], False, "typed_expected"),
    ("research", "Compare the specs of four laptops across three shopping sites", None, "typed", [S], False, "typed_expected"),
    ("research", "Research the history of the abacus and give me sources", None, "typed", [S], False, "typed_expected"),
    ("research", "Gather reviews of this restaurant from three review sites", None, "typed", [S], False, "typed_expected"),
]

CASES = [
    {"id": f"E{i + 1:03d}", "category": c, "task": t, "page_path": p, "execution": e, "perception": sorted(pe), "ambiguous": a, "value": v}
    for i, (c, t, p, e, pe, a, v) in enumerate(_CASES)
]


def set_hash() -> str:
    return hashlib.sha256(json.dumps(CASES, sort_keys=True).encode()).hexdigest()


if __name__ == "__main__":
    from collections import Counter
    print(len(CASES), "cases;", dict(Counter(c["category"] for c in CASES)))
    print("execution labels:", dict(Counter(c["execution"] for c in CASES)))
    print("sha256", set_hash())
