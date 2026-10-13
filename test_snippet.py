import re

def get_query_focused_excerpt(text: str, query: str, max_len: int = 500) -> str:
    if len(text) <= max_len:
        return text
        
    # Find all alphanumeric words in query
    query_words = [w.lower() for w in re.findall(r'\w+', query) if len(w) > 3]
    if not query_words:
        return text[:max_len-3] + "..."
        
    lower_text = text.lower()
    best_idx = 0
    
    for word in query_words:
        idx = lower_text.find(word)
        if idx != -1:
            best_idx = idx
            break
            
    # Center the snippet around best_idx
    start = max(0, best_idx - 100)
    end = min(len(text), start + max_len - 3)
    
    # adjust start to align if we hit the end
    if end == len(text):
        start = max(0, end - max_len + 3)
        
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet[3:]
    if end < len(text):
        snippet = snippet + "..."
        
    return snippet

text = "Project Specification\n\n" + ("Filler content. " * 40) + "\nTHERE_IS_A_UNIQUE_SECRET_SENTINEL_AT_THE_END_984731"
query = "THERE_IS_A_UNIQUE_SECRET_SENTINEL_AT_THE_END_984731"
print(get_query_focused_excerpt(text, query))

