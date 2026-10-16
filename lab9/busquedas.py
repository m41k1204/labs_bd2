from bow import fetch_data_bow, preprocess, compute_bow, fetch_stopwords, fetch_data, connect_db
import pandas as pd
import math

stopwords = fetch_stopwords()

def boolean_search_linear(query, dataframe):
  partes = query.split()
  condicion = partes[1]
  partes.pop(1)
  terminos = " ".join(partes)
  query_stemmeada = preprocess(terminos, stopwords)

  result = []
  for index, row in dataframe.iterrows():
    if condicion == "AND":
      if query_stemmeada[0] in row["bag_of_words"] and query_stemmeada[1] in row["bag_of_words"]:
        result.append(row)
    elif condicion == "OR":
      if query_stemmeada[0] in row["bag_of_words"] or query_stemmeada[1] in row["bag_of_words"]:
        result.append(row)
    else:
      if query_stemmeada[0] in row["bag_of_words"] and not query_stemmeada[1] in row["bag_of_words"]:
        result.append(row)

  return result

# noticias_bow_df = fetch_data_bow()
# print(boolean_search_linear("economía AND inflación",noticias_bow_df))
# print(boolean_search_linear("banca OR finanzas",noticias_bow_df))
# print(boolean_search_linear("tecnología AND-NOT inflación", noticias_bow_df))


class InvertedIndex:
  def __init__(self):
    self.index = {}
    self.idf = {}
    self.length = {}
    self._docs = {}
    self._bows = {}

  def build_from_db(self):
      # Leer desde PostgreSQL todos los bag of words
      conn = connect_db()
      df = pd.read_sql("SELECT id, contenido, bag_of_words FROM noticias ORDER BY id;", conn)
      conn.close()
      # Construir el índice invertido, el idf y la norma (longitud) de cada documento

      # Paso 1: indice invertido, textos y bows por documento
      for index, row in df.iterrows():
        doc_id = int(row["id"])
        bow = row["bag_of_words"]
        self._docs[doc_id] = row["contenido"]
        self._bows[doc_id] = bow
        for word in bow:
          tf = bow[word]
          if word not in self.index:
            self.index[word] = []
          self.index[word].append((doc_id, tf))

      # Paso 2: idf de cada palabra
      N = len(self._bows)
      for word in self.index:
        df_word = len(self.index[word])
        self.idf[word] = math.log10(N / df_word)

      # Paso 3: norma de cada documento
      for doc_id in self._bows:
        bow = self._bows[doc_id]
        suma = 0
        for word in bow:
          tf = bow[word]
          w = math.log10(1 + tf) * self.idf[word]
          suma += w * w
        self.length[doc_id] = math.sqrt(suma)

  def L(self, word):
    stems = preprocess(word, stopwords)
    if len(stems) == 0:
      return []
    return self.index.get(stems[0], [])

  def showDocument(self, doc_id, max_chars=80):
    return self._docs.get(doc_id, "")[:max_chars] + "..."

  def showDocuments(self, posting_list, max_chars=80):
    return [self.showDocument(doc_id, max_chars) for doc_id, *_ in posting_list]

  def query_weights(self, query):
    # Paso 1: bow de la query
    bow_query = compute_bow(query, stopwords)

    # Paso 2: peso tf-idf de cada termino y norma de la query
    weights = {}
    suma = 0
    for word in bow_query:
      if word in self.idf:
        tf = bow_query[word]
        w = math.log10(1 + tf) * self.idf[word]
        weights[word] = w
        suma += w * w
    norma = math.sqrt(suma)
    return weights, norma

  def cosine_search_linear(self, query, top_k=5):
    # Implementar la búsqueda por similitud de coseno lineal
    score = {}
    weights, norma_query = self.query_weights(query)
    if norma_query == 0:
      return []

    for doc_id in self._bows:
      bow = self._bows[doc_id]

      suma = 0
      for word in bow:
        w_doc = math.log10(1 + bow[word]) * self.idf[word]
        suma += w_doc * w_doc
      norma_doc = math.sqrt(suma)
      if norma_doc == 0:
        continue

      punto = 0
      for word in weights:
        if word in bow:
          w_doc = math.log10(1 + bow[word]) * self.idf[word]
          punto += weights[word] * w_doc

      if punto > 0:
        score[doc_id] = punto / (norma_query * norma_doc)

    return sorted(score.items(), key=lambda t: t[1], reverse=True)[:top_k]

  def cosine_search(self, query, top_k=5):
    score = {}
  # Implementar la búsqueda por similitud de coseno con índice invertido
    weights, norma_query = self.query_weights(query)
    if norma_query == 0:
      return []

    for word in weights:
      for doc_id, tf in self.index[word]:
        w_doc = math.log10(1 + tf) * self.idf[word]
        if doc_id not in score:
          score[doc_id] = 0
        score[doc_id] += weights[word] * w_doc

    for doc_id in score:
      score[doc_id] = score[doc_id] / (norma_query * self.length[doc_id])

    return sorted(score.items(), key=lambda t: t[1], reverse=True)[:top_k]

def AND(list1, list2):
  result = []
  l1 = 0
  l2 = 0
  while True:
    if l1 >= len(list1) or l2 >= len(list2):
      break
    if list1[l1][0] == list2[l2][0]:
      result.append(list1[l1])
      l1 += 1
      l2 += 1
    elif list1[l1][0] < list2[l2][0]:
      l1 += 1
    else: 
      l2 += 1
  return result
  
def OR(list1, list2):
  result = []
  l1 = 0
  l2 = 0
  while True:
    if l1 >= len(list1) or l2 >= len(list2):
      break
    if list1[l1][0] == list2[l2][0]:
      result.append(list1[l1])
      l1 += 1
      l2 += 1
    elif list1[l1][0] < list2[l2][0]:
      result.append(list1[l1])
      l1 += 1
    else:
      result.append(list2[l2])
      l2 += 1

  while l1 < len(list1):
    result.append(list1[l1])
    l1 += 1

  while l2 < len(list2):
    result.append(list2[l2])
    l2 += 1
  return result
  
def AND_NOT(list1, list2):
  result = []
  l1 = 0
  l2 = 0
  while True:
    if l1 >= len(list1) or l2 >= len(list2):
      break
    if list1[l1][0] == list2[l2][0]:
      l1 += 1
      l2 += 1
    elif list1[l1][0] < list2[l2][0]:
      result.append(list1[l1])
      l1 += 1
    else:
      l2 += 1

  while l1 < len(list1):
    result.append(list1[l1])
    l1 += 1

  return result
idx = InvertedIndex()
idx.build_from_db()

pruebas = [
  ("sostenibilidad AND (ambiente AND renovables)", AND(idx.L("sostenibilidad"), AND(idx.L("ambiente"), idx.L("renovables")))),
  ("tecnología AND (banca OR finanzas)", AND(idx.L("tecnología"), OR(idx.L("banca"), idx.L("finanzas")))),
  ("economía AND-NOT inflación", AND_NOT(idx.L("economía"), idx.L("inflación"))),
  ("(banca OR finanzas) AND-NOT tecnología", AND_NOT(OR(idx.L("banca"), idx.L("finanzas")), idx.L("tecnología"))),
  ("bitcoin OR (criptomonedas OR blockchain)", OR(idx.L("bitcoin"), OR(idx.L("criptomonedas"), idx.L("blockchain")))),
  ("crédito AND (vivienda AND-NOT pandemia)", AND(idx.L("crédito"), AND_NOT(idx.L("vivienda"), idx.L("pandemia")))),
]

for descripcion, resultado in pruebas:
  print()
  print(descripcion, "->", len(resultado), "documentos")
  print(idx.showDocuments(resultado[:3]))

queries = [
  "innovaciones en banca digital y tecnología financiera",
  "inflación y crecimiento económico",
  "sostenibilidad y energías renovables"
]
for q in queries:
  print(f"\n{q}")
  print("Lineal :", idx.cosine_search_linear(q, 5))
  print("Índice :", idx.cosine_search(q, 5))
