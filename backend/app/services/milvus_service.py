from pymilvus import connections, utility, FieldSchema, CollectionSchema, DataType, Collection
from typing import List, Dict, Any
from app.core.config import settings
from collections import Counter, defaultdict

class MilvusService:
    def __init__(self):
        self.alias = "default"
        self._connect()

    def _connect(self):
        # Connect to Zilliz/Milvus
        # Note: In production, handle disconnections/retries
        try:
            connections.connect(
                alias=self.alias, 
                uri=settings.MILVUS_URI, 
                token=settings.MILVUS_TOKEN
            )
            print(f"Successfully connected to Milvus (Alias: {self.alias})")
        except Exception as e:
            print(f"Failed to connect to Milvus: {e}")

    def check_connection(self):
        if not connections.has_connection(self.alias):
            print("Connection missing, attempting reconnect...")
            self._connect()

    def get_collection_name(self, client_name: str) -> str:
        # Sanitize client name for collection
        safe_name = "".join(x for x in client_name if x.isalnum() or x == "_")
        return f"{safe_name}_products"

    def ensure_collection(self, client_name: str, recreate: bool = False):
        self.check_connection()
        collection_name = self.get_collection_name(client_name)
        
        if recreate and utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
        
        if utility.has_collection(collection_name):
            return Collection(collection_name)
            
        # Define Schema (Flattened: One Image = One Row)
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="product_id", dtype=DataType.INT64), # Shopify Product ID
            FieldSchema(name="image_id", dtype=DataType.INT64),   # Shopify Image ID
            FieldSchema(name="store_id", dtype=DataType.INT64),   # Storefront ID
            FieldSchema(name="sku", dtype=DataType.VARCHAR, max_length=100), # SKU for Dedup
            FieldSchema(name="view_type", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=512) # CLIP dim
        ]
        
        schema = CollectionSchema(fields, f"Product images for {client_name}")
        collection = Collection(collection_name, schema)
        
        # Create Index
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        
        # Create Scalar Index for SKU (faster lookups)
        # collection.create_index(field_name="sku", index_name="sku_index") 
        # (Optional, Milvus usually handles scalar filters ok)
        
        collection.load()
        return collection

    async def check_existing_skus(self, client_name: str, skus: List[str]) -> set:
        """
        Check which of the provided SKUs already exist in the collection.
        Returns a set of existing SKUs.
        """
        if not skus:
            return set()
            
        collection_name = self.get_collection_name(client_name)
        if not utility.has_collection(collection_name):
            return set()
            
        collection = Collection(collection_name)
        collection.load()
        
        # Expression to match any of the SKUs
        # sku in ["abc", "def"]
        safe_skus = [s.replace('"', '\\"') for s in skus] # Basic Sanitization
        expr = f'sku in {str(safe_skus)}'
        
        res = collection.query(
            expr=expr,
            output_fields=["sku"],
            consistency_level="Strong"
        )
        
        existing = {item["sku"] for item in res}
        return existing
        
    async def count_product_vectors(self, client_name: str, product_id: int) -> int:
        """
        Count how many vectors exist for a given product ID.
        """
        self.check_connection()
        collection_name = self.get_collection_name(client_name)
        if not utility.has_collection(collection_name):
            return 0
            
        collection = Collection(collection_name)
        collection.load()
        
        res = collection.query(
            expr=f"product_id == {product_id}",
            output_fields=["id"],
            consistency_level="Strong"
        )
        return len(res)
        
    async def upsert_vectors(self, client_name: str, vectors: List[Dict[str, Any]], recreate_schema: bool = False):
        """
        vectors format: [{"product_id": 1, "image_id": 2, "store_id": 1, "sku": "ABC", ...}]
        """
        if not vectors:
            return
            
        collection = self.ensure_collection(client_name, recreate=recreate_schema)
        
        # Insert (Milvus insert returns mutation result)
        # Prepare columnar data
        data = [
            [v["product_id"] for v in vectors],
            [v["image_id"] for v in vectors],
            [v["store_id"] for v in vectors],
            [v.get("sku", "") for v in vectors], # Add SKU
            [v["view_type"] for v in vectors],
            [v["embedding"] for v in vectors]
        ]
        
        collection.insert(data)
        collection.flush()

    async def search_image(self, client_name: str, query_vector: List[float], top_k: int = 20) -> List[Dict[str, Any]]:
        """
        Implements MAJORITY VOTING.
        1. Search Top-K raw vectors.
        2. Aggregate results by product_id.
        3. Rank products by (Frequency, Max Score).
        """
        collection = self.ensure_collection(client_name)
        
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        
        results = collection.search(
            data=[query_vector], 
            anns_field="embedding", 
            param=search_params, 
            limit=top_k, 
            output_fields=["product_id", "store_id", "view_type"]
        )
        
        # Aggregate logic
        hits = results[0] # Single query
        
        product_votes = Counter()
        product_scores = defaultdict(float)
        product_stores = {}
        
        for hit in hits:
            pid = hit.entity.get("product_id")
            score = hit.score
            
            # Only include if similarity >= 50% to filter out weak matches
            if score >= 0.5:
                product_votes[pid] += 1
                product_scores[pid] = max(product_scores[pid], score) # Keep best score
                product_stores[pid] = hit.entity.get("store_id")
            
        # Sort by Votes (Validation), then Score (Similarity)
        ranked_products = sorted(
            product_votes.keys(), 
            key=lambda pid: (product_votes[pid], product_scores[pid]), 
            reverse=True
        )
        
        # Format Result
        final_results = []
        for pid in ranked_products[:10]: # Return Top 10 Products
            final_results.append({
                "product_id": pid,
                "store_id": product_stores[pid],
                "vote_count": product_votes[pid],
                "best_score": product_scores[pid]
            })
            
        return final_results

milvus_service = MilvusService()
