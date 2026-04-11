import json
import os
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import chromadb
from chromadb.utils import embedding_functions

def main():
    data_path = "../codes/code_0F/data_analysis/output_normalized.json"
    if not os.path.exists(data_path):
        print(f"Normalized data not found: {data_path}")
        return
        
    with open(data_path, "r") as f:
        data = json.load(f)
        
    client = chromadb.PersistentClient(path="./chroma_db")
    
    print("Loading embedding model...")
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(name="code_segments", embedding_function=sentence_transformer_ef)
    
    print(f"Embedding {len(data)} snippets...")
    docs = []
    metas = []
    ids = []
    for idx, item in enumerate(data):
        code = item.get("normalized_code", item.get("original_code", ""))
        func = item.get("function", "unknown")
        docs.append(code.strip())
        metas.append({"function": func})
        ids.append(f"code_{idx}")
        
    collection.add(
        documents=docs,
        metadatas=metas,
        ids=ids
    )
        
    print("Vector database populated successfully in ./chroma_db!")

if __name__ == "__main__":
    main()
import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

def main():
    data_path = "../codes/code_0F/data_analysis/output_normalized.json"
    if not os.path.exists(data_path):
        print(f"Normalized data not found: {data_path}")
        return
        
    with open(data_path, "r") as f:
        data = json.load(f)
        
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(name="code_segments")
    
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print(f"Embedding {len(data)} snippets...")
    for idx, item in enumerate(data):
        code = item.get("normalized_code", item.get("original_code", ""))
        func = item.get("function", "unknown")
        
        embedding = model.encode(code).tolist()
        
        collection.add(
            embeddings=[embedding],
            documents=[code],
            metadatas=[{"function": func}],
            ids=[f"code_{idx}"]
        )
        
    print("Vector database populated successfully in ./chroma_db!")

if __name__ == "__main__":
    main()
