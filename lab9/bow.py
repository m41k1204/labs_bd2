import psycopg2, pandas as pd, json, time, math, re
import matplotlib.pyplot as plt
from nltk.stem.snowball import SnowballStemmer

stemmer = SnowballStemmer("spanish")

def connect_db():
  conn = psycopg2.connect(
    dbname="lab9", user="postgres",
    password="postgres", host="localhost", port="5434"
  )
  return conn

def fetch_data():
  conn = connect_db()
  df = pd.read_sql("SELECT id, contenido FROM noticias;", conn)
  conn.close()
  return df

def fetch_stopwords():
  conn = connect_db()
  df = pd.read_sql("SELECT word FROM stopwords;", conn)
  conn.close()
  return set(df["word"])

def preprocess(text, stopwords):
  # Aplicar todos los pasos de preprocesamiento (minúsculas, tokenización, stopwords, stemming)
  # Paso 1: minusculas
  text = text.lower()

  # Paso 2: tokenizacion
  words = re.findall(r"[a-záéíóúñü]+", text)

  # Paso 3: Stopwords
  finales = []
  for word in words:
    if word not in stopwords:
      finales.append(word)

  # Paso 4: Stemming
  stems = []
  for word in finales:
    stems.append(stemmer.stem(word))
  return stems

def compute_bow(text, stopwords):
  # Aplicar la función de preprocesamiento y calcular el Bag of Words (frecuencia de términos)
  # Paso 1: preprocesamiento
  stemmed_words = preprocess(text, stopwords)

  # Paso 2: calcular bow
  bow = {}
  for word in stemmed_words:
    if word in bow:
      bow[word] += 1
    else:
      bow[word] = 1
  return bow

def update_bow_in_db(dataframe, stopwords):
# Actualizar la columna bag_of_words de la tabla noticias con el BoW calculado para cada documento
  conn = connect_db()
  cursor = conn.cursor()
  for index, row in dataframe.iterrows():
    bow = compute_bow(row["contenido"], stopwords)
    bow_json = json.dumps(bow)
    cursor.execute(
      "UPDATE noticias SET bag_of_words = %s WHERE id = %s;",
      (bow_json, int(row["id"]))
    )
  conn.commit()
  cursor.close()
  conn.close()

def fetch_data_bow():
# Mostrar las primeras 10 filas de la tabla noticias_bow
  conn = connect_db()
  df = pd.read_sql("SELECT * FROM noticias;", conn)
  conn.close()
  return df

if __name__ == "__main__":
  stopwords = fetch_stopwords()
  noticias_df = fetch_data()
  update_bow_in_db(noticias_df, stopwords)
  noticias_bow_df = fetch_data_bow()
  print(noticias_bow_df.head(10))
