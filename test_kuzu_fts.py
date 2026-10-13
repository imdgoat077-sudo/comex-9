import kuzu
db = kuzu.Database("test_fts.db")
conn = kuzu.Connection(db)
conn.execute("CREATE NODE TABLE Doc(id STRING, text STRING, PRIMARY KEY (id))")
conn.execute("CALL CREATE_FTS_INDEX('Doc', 'Doc_FTS', ['text'])")
conn.execute("CREATE (d:Doc {id: '1', text: 'This is some filler text to make the document longer. ' + 'filler ' * 50 + 'And here is the secret sentinel.'})")
try:
    res = conn.execute("CALL QUERY_FTS_INDEX('Doc', 'Doc_FTS', 'secret') YIELD node, score RETURN node, score")
    while res.has_next():
        node, score = res.get_next()
        print("MATCHED NODE:", node)
except Exception as e:
    print(e)
