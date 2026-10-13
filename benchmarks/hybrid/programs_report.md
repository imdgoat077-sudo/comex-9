# Typed tools vs browser programs

Same tasks, same model, same isolated headless Chrome and backend per mode; success read from the page.
Modes: **typed** = programs switched off; **hybrid** = the agent chooses; **program** = the prompt asks for one browser_program call. Medians over the trials; ranges in brackets.

| Scenario | Mode | Success | Quality | Wall time | Model calls | Model time | Browser time | Failed calls | Recovered | Programs |
|---|---|---|---|---|---|---|---|---|---|---|
| sheet | typed | 3/3 | 1.00 | 44.9 s (44–58 s) | 8 | 42.2 s | 2.6 s | 0 | 0 | 0 |
| sheet | hybrid | 3/3 | 1.00 | 35.3 s (29–140 s) | 8 | 31.6 s | 3.3 s | 8 | 3 | 10 |
| sheet | program | 3/3 | 1.00 | 28.3 s (26–38 s) | 3 | 24.8 s | 3.2 s | 2 | 2 | 5 |
| excalidraw | typed | 3/3 | 1.00 | 34.2 s (25–35 s) | 8 | 32.7 s | 1.2 s | 0 | 0 | 0 |
| excalidraw | hybrid | 3/3 | 1.00 | 29.9 s (24–33 s) | 6 | 28.9 s | 1.0 s | 0 | 0 | 0 |
| excalidraw | program | 3/3 | 1.00 | 32.8 s (20–82 s) | 2 | 28.9 s | 2.9 s | 4 | 1 | 10 |
| chess | typed | 3/3 | 1.00 | 24.4 s (24–33 s) | 5 | 24.0 s | 0.2 s | 1 | 1 | 0 |
| chess | hybrid | 3/3 | 1.00 | 23.8 s (22–27 s) | 5 | 23.5 s | 0.2 s | 0 | 0 | 0 |
| chess | program | 3/3 | 1.00 | 57.9 s (55–78 s) | 6 | 54.1 s | 1.0 s | 4 | 2 | 13 |
| wordle | typed | 3/3 | 1.00 | 51.8 s (42–62 s) | 12 | 47.3 s | 4.5 s | 0 | 0 | 0 |
| wordle | hybrid | 3/3 | 1.00 | 61.6 s (49–121 s) | 12 | 54.5 s | 7.0 s | 3 | 2 | 9 |
| wordle | program | 3/3 | 1.00 | 149.2 s (55–223 s) | 6 | 144.9 s | 8.3 s | 6 | 2 | 22 |

## Failures

None.

## Per trial

| Scenario | Mode | Trial | Pass | Wall | Tools | Programs | Failed calls | Tools used |
|---|---|---|---|---|---|---|---|---|
| sheet | typed | 1 | yes | 57.85 s | 11 | 0 | 0 | browser_evaluate, browser_keys, browser_observe, browser_pointer |
| sheet | typed | 2 | yes | 44.9 s | 7 | 0 | 0 | browser_click, browser_evaluate, browser_keys |
| sheet | typed | 3 | yes | 44.31 s | 7 | 0 | 0 | browser_click, browser_evaluate, browser_keys, browser_observe |
| sheet | hybrid | 1 | yes | 35.32 s | 7 | 2 | 1 | browser_evaluate, browser_inspect, browser_observe, browser_program |
| sheet | hybrid | 2 | yes | 29.27 s | 5 | 2 | 1 | browser_evaluate, browser_observe, browser_program |
| sheet | hybrid | 3 | yes | 140.23 s | 30 | 6 | 6 | browser_evaluate, browser_keys, browser_observe, browser_program, browser_sequence |
| sheet | program | 1 | yes | 28.33 s | 2 | 2 | 1 | browser_program |
| sheet | program | 2 | yes | 37.5 s | 2 | 2 | 1 | browser_program |
| sheet | program | 3 | yes | 25.85 s | 1 | 1 | 0 | browser_program |
| excalidraw | typed | 1 | yes | 34.18 s | 7 | 0 | 0 | browser_click, browser_find, browser_inspect, browser_pointer, browser_screenshot |
| excalidraw | typed | 2 | yes | 35.41 s | 7 | 0 | 0 | browser_click, browser_find, browser_inspect, browser_pointer, browser_screenshot |
| excalidraw | typed | 3 | yes | 24.75 s | 6 | 0 | 0 | browser_click, browser_find, browser_inspect, browser_screenshot, browser_sequence |
| excalidraw | hybrid | 1 | yes | 29.93 s | 5 | 0 | 0 | browser_evaluate, browser_find, browser_screenshot, browser_sequence |
| excalidraw | hybrid | 2 | yes | 32.83 s | 6 | 0 | 0 | browser_evaluate, browser_find, browser_keys, browser_screenshot, browser_sequence |
| excalidraw | hybrid | 3 | yes | 24.01 s | 3 | 0 | 0 | browser_inspect, browser_screenshot, browser_sequence |
| excalidraw | program | 1 | yes | 82.2 s | 9 | 8 | 4 | browser_program, browser_screenshot |
| excalidraw | program | 2 | yes | 32.78 s | 1 | 1 | 0 | browser_program |
| excalidraw | program | 3 | yes | 20.11 s | 1 | 1 | 0 | browser_program |
| chess | typed | 1 | yes | 33.11 s | 5 | 0 | 1 | browser_evaluate, browser_sequence |
| chess | typed | 2 | yes | 24.36 s | 4 | 0 | 0 | browser_evaluate, browser_sequence |
| chess | typed | 3 | yes | 23.55 s | 4 | 0 | 0 | browser_evaluate, browser_sequence |
| chess | hybrid | 1 | yes | 23.84 s | 4 | 0 | 0 | browser_evaluate, browser_sequence |
| chess | hybrid | 2 | yes | 27.19 s | 4 | 0 | 0 | browser_evaluate, browser_sequence |
| chess | hybrid | 3 | yes | 21.57 s | 4 | 0 | 0 | browser_evaluate, browser_sequence |
| chess | program | 1 | yes | 55.05 s | 5 | 5 | 2 | browser_program |
| chess | program | 2 | yes | 77.65 s | 5 | 5 | 2 | browser_program |
| chess | program | 3 | yes | 57.86 s | 3 | 3 | 0 | browser_program |
| wordle | typed | 1 | yes | 41.79 s | 8 | 0 | 0 | browser_evaluate, browser_sequence |
| wordle | typed | 2 | yes | 61.96 s | 16 | 0 | 0 | browser_evaluate, browser_keys, browser_wait |
| wordle | typed | 3 | yes | 51.84 s | 11 | 0 | 0 | browser_evaluate, browser_keys, browser_wait |
| wordle | hybrid | 1 | yes | 120.83 s | 17 | 5 | 1 | browser_evaluate, browser_keys, browser_program, browser_wait |
| wordle | hybrid | 2 | yes | 61.62 s | 11 | 0 | 0 | browser_evaluate, browser_keys, browser_observe, browser_wait |
| wordle | hybrid | 3 | yes | 49.28 s | 8 | 4 | 2 | browser_evaluate, browser_program, browser_sequence |
| wordle | program | 1 | yes | 149.2 s | 5 | 3 | 2 | browser_evaluate, browser_program |
| wordle | program | 2 | yes | 222.61 s | 18 | 16 | 4 | browser_evaluate, browser_program |
| wordle | program | 3 | yes | 54.79 s | 3 | 3 | 0 | browser_program |
