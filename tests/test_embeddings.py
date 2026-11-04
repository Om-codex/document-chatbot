from embeddings.embedding_model import get_embedding_model

embedding_model = get_embedding_model()

text = "Machine Learning is a subset of Artificial Intelligence"

vector = embedding_model.embed_query(text)
print("Embedding generated successfully")
print("Vector dimensions: ",len(vector))