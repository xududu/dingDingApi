import jieba

result = jieba.tokenize(u'authority的domain发到zw4')
for tk in result:
    # print("word %s\t\t start: %d \t\t end:%d" % (tk[0],tk[1],tk[2]))
    print(tk)