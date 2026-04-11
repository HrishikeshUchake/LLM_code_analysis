import sys
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import chromadb
from chromadb.utils import embedding_functions

def main():
    if len(sys.argv) < 2:
        print("Usage: python query_rag.py <query_code_snippet>")
        return
        
    query = " ".join(sys.argv[1:])
    
    client = chromadb.PersistentClient(path="./chroma_db")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    
    try:
        collection = client.get_collection(name="code_segments", embedding_function=sentence_transformer_ef)
    except ValueError:
        print("Collection not found. Please run build_vector_db.py first.")
        return
        
    results = collection.query(
        query_texts=[query],
        n_results=3
    )
    
    print("\n--- RAG Retrieval Results ---")
    for i in range(len(results['documents'][0])):
        print(f"\n[Result {i+1}] Metadata: {results['metadatas'][0][i]}")
        print("Code:")
        print(results['documents'][0][i])

if __name__ == "__main__":
    main()
