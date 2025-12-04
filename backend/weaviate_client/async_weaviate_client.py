import asyncio
import os
from typing import Literal, Optional, List, Dict

import weaviate
import weaviate.classes as wvc
from weaviate.classes.config import Property, DataType, Configure, VectorDistances
from weaviate.classes.query import Filter
from weaviate.connect import ConnectionParams
from weaviate.classes.init import AdditionalConfig, Timeout
from dotenv import load_dotenv

load_dotenv()



async def connect_to_weaviate(
    provider: Literal["google_studio", "vertex_ai"] = "google_studio"
) -> weaviate.WeaviateAsyncClient:

    headers = {}
    if provider == "google_studio":
        # Gemini API authentication
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY or GEMINI_API_KEY must be set in environment for Google AI Studio. "
                "Get your API key from: https://makersuite.google.com/app/apikey"
            )
        headers = {
            "X-Goog-Studio-Api-Key": api_key,  # Note: Capital letters as per Weaviate docs
        }
    elif provider == "vertex_ai":
        # Vertex AI authentication
        # Check if manual token is provided
        vertex_token = os.getenv("VERTEX_AI_ACCESS_TOKEN")
        if vertex_token:
            # Manual token mode - user manages token refresh
            headers = {
                "X-Goog-Vertex-Api-Key": vertex_token,
            }
        else:
            # Automatic token generation mode
            # Requires USE_GOOGLE_AUTH=true in Weaviate server environment
            # and properly configured Google Application Default Credentials
            use_google_auth = os.getenv("USE_GOOGLE_AUTH", "").lower() == "true"
            if not use_google_auth:
                raise ValueError(
                    "For Vertex AI, either:\n"
                    "1. Set VERTEX_AI_ACCESS_TOKEN with your access token (manual mode), OR\n"
                    "2. Set USE_GOOGLE_AUTH=true and configure Google Application Default Credentials\n"
                    "   Run: gcloud auth application-default login\n"
                    "   See: https://docs.weaviate.io/weaviate/model-providers/google/embeddings#automatic-token-generation"
                )
            # If USE_GOOGLE_AUTH=true, Weaviate server handles token generation automatically
            # No headers needed in this case
    else:
        raise ValueError("provider must be one of 'google_studio' or 'vertex_ai'")

    client = weaviate.WeaviateAsyncClient(
        connection_params=ConnectionParams.from_params(
            http_host=os.getenv("WEAVIATE_HOST", "localhost"),
            http_port=int(os.getenv("WEAVIATE_PORT", "8081")),
            http_secure=False,
            grpc_host=os.getenv("WEAVIATE_GRPC_HOST", "localhost"),
            grpc_port=int(os.getenv("WEAVIATE_GRPC_PORT", "50051")),
            grpc_secure=False,
        ),
        additional_headers=headers,
        additional_config=AdditionalConfig(
            timeout=Timeout(init=30, query=60, insert=120),
        ),
        skip_init_checks=False,
    )

    await client.connect()
    return client


async def close_connection(client: weaviate.WeaviateAsyncClient) -> None:

    await client.close()


class get_weaviate_client:
    """
    Async context manager for Weaviate client that handles connection lifecycle.
    
    This ensures proper connection and cleanup, preventing resource leaks.
    
    Example:
        async with get_weaviate_client("google_studio") as client:
            collection = await create_collection(client, "MyCollection")
            # ... use client ...
        # Connection is automatically closed when exiting context
    """
    
    def __init__(self, provider: Literal["google_studio", "vertex_ai"] = "google_studio"):
        self.provider = provider
        self.client: Optional[weaviate.WeaviateAsyncClient] = None
    
    async def __aenter__(self) -> weaviate.WeaviateAsyncClient:
        self.client = await connect_to_weaviate(self.provider)
        return self.client
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.close()


async def create_collection(
    client: weaviate.WeaviateAsyncClient,
    class_name: str,
    provider: Literal["google_studio", "vertex_ai"] = "google_studio",
    model_id: str = "gemini-embedding-001",
    delete_if_exists: bool = True,
) -> weaviate.collections.Collection:

    # Optionally delete existing class
    if delete_if_exists:
        try:
            await client.collections.delete(class_name)
        except Exception:
            pass

    # Configure vectorizer based on provider
    if provider == "google_studio":
        # Gemini API vectorizer (text2vec-google-aistudio)
        vectorizer = Configure.Vectorizer.text2vec_google_aistudio(
            model_id=model_id,
            vectorize_collection_name=False,
        )
    elif provider == "vertex_ai":
        # Vertex AI vectorizer (text2vec-google)
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT must be set in environment for Vertex AI usage.\n"
                "This is your GCP project ID where Vertex AI is enabled."
            )
        
        vectorizer = Configure.Vectorizer.text2vec_google(
            project_id=project_id,
            model_id=model_id,
            vectorize_collection_name=False,    
        )
    else:
        raise ValueError("provider must be 'google_studio' or 'vertex_ai'")

    # Create collection with HNSW vector index
    cls = await client.collections.create(
        name=class_name,
        description=f"Collection using Google {model_id} embeddings with HNSW vector index",
        vector_index_config=Configure.VectorIndex.hnsw(
                distance_metric=VectorDistances.COSINE,
                vector_cache_max_objects=100_000,
            ),
        vectorizer_config=vectorizer,
        properties=[
            Property(
                name="customer_query",
                data_type=DataType.TEXT,
                description="The customer's query or question",
                vectorize_property_name=True,
            ),
            Property(
                name="agent_responses",
                data_type=DataType.OBJECT,
                description="The agent's response details",
                vectorize_property_name=False,
                skip_vector_index=True,
                nested_properties=[
                    Property(
                        name="customer_query",
                        data_type=DataType.TEXT,
                        description="The customer query (duplicate for reference)",
                        skip_vector_index=True,
                    ),
                    Property(
                        name="agent_script",
                        data_type=DataType.TEXT,
                        description="The agent's scripted response",
                        skip_vector_index=True,
                    ),
                    Property(
                        name="actions",
                        data_type=DataType.TEXT,
                        description="Actions to be taken",
                        skip_vector_index=True,
                    ),
                    Property(
                        name="category",
                        data_type=DataType.TEXT,
                        description="Response category",
                        skip_vector_index=True,
                    ),
                    Property(
                        name="subcategory",
                        data_type=DataType.TEXT,
                        description="Response subcategory",
                        skip_vector_index=True,
                    ),
                    Property(
                        name="notes",
                        data_type=DataType.TEXT,
                        description="Additional notes",
                        skip_vector_index=True,
                    ),
                ],
            ),
            Property(
                name="scenario",
                data_type=DataType.TEXT,
                description="The scenario of the query and content",
                vectorize_property_name=False,
            ),
        ],
    )

    return cls


async def delete_collection(
    client: weaviate.WeaviateAsyncClient,
    class_name: str
) -> bool:

    try:
        await client.collections.delete(class_name)
        return True
    except Exception:
        return False


async def insert_data(
    client: weaviate.WeaviateAsyncClient, 
    data_objects: List[Dict], 
    collection_name: str
) -> Dict:
    """
    Insert data into a collection using Weaviate's native batch insert.
    
    This method uses Weaviate's built-in insert_many which is optimized for
    batch operations and significantly more efficient than individual inserts.
    
    Note: This function will fail if the collection doesn't exist. Collections must
    be created first using create_collection() with proper vectorizer configuration.
    
    Args:
        client: Connected Weaviate async client
        data_objects: List of dictionaries containing object properties
        collection_name: Name of the collection to insert into
        
    Returns:
        Dict with 'inserted_count', 'failed_count', and 'errors' (if any)
        
    Raises:
        ValueError: If the collection doesn't exist
    """
    # Check if collection exists first
    exists = await collection_exists(client, collection_name)
    if not exists:
        raise ValueError(
            f"Collection '{collection_name}' does not exist. "
            f"Please create the collection first with proper vectorizer configuration using create_collection()."
        )
    
    # Get collection (note: collections.get() is sync, doesn't need await)
    collection = client.collections.get(collection_name)
    
    # Insert data using Weaviate's native async insert_many method
    response = await collection.data.insert_many(data_objects)
    
    # Check for errors in the response
    failed_count = 0
    errors = []
    
    if response.has_errors:
        for uuid, error in response.errors.items():
            failed_count += 1
            errors.append({
                "uuid": str(uuid) if uuid else None,
                "error": str(error)
            })
    
    return {
        "inserted_count": len(data_objects) - failed_count,
        "failed_count": failed_count,
        "errors": errors if errors else None,
        "all_response": response
    }


async def insert_single_object(
    client: weaviate.WeaviateAsyncClient,
    data_object: Dict,
    collection_name: str,
    uuid: Optional[str] = None
) -> Dict:
    """
    Insert a single object into a collection using async client.
    
    Args:
        client: Connected Weaviate async client
        data_object: Dictionary containing object properties
        collection_name: Name of the collection to insert into
        uuid: Optional UUID for the object
        
    Returns:
        Dict with 'uuid' and 'success' status
        
    Raises:
        ValueError: If the collection doesn't exist
    """
    # Check if collection exists first
    exists = await collection_exists(client, collection_name)
    if not exists:
        raise ValueError(
            f"Collection '{collection_name}' does not exist. "
            f"Please create the collection first with proper vectorizer configuration using create_collection()."
        )
    
    collection = client.collections.get(collection_name)
    
    try:
        # Insert single object
        inserted_uuid = await collection.data.insert(
            properties=data_object,
            uuid=uuid
        )
        return {
            "uuid": str(inserted_uuid),
            "success": True,
            "error": None
        }
    except Exception as e:
        return {
            "uuid": uuid,
            "success": False,
            "error": str(e)
        }


async def update_single_object(
    client: weaviate.WeaviateAsyncClient,
    uuid: str,
    data_object: Dict,
    collection_name: str
) -> Dict:
    """
    Update a single object in a collection using async client.
    
    Args:
        client: Connected Weaviate async client
        uuid: UUID of the object to update
        data_object: Dictionary containing properties to update
        collection_name: Name of the collection
        
    Returns:
        Dict with 'uuid', 'success' status, and error if any
        
    Raises:
        ValueError: If the collection doesn't exist
    """
    
    collection = client.collections.get(collection_name)
    
    try:
        # Update single object
        await collection.data.update(
            uuid=uuid,
            properties=data_object
        )
        return {
            "uuid": uuid,
            "success": True,
            "error": None
        }
    except Exception as e:
        return {
            "uuid": uuid,
            "success": False,
            "error": str(e)
        }


async def update_many_objects(
    client: weaviate.WeaviateAsyncClient,
    updates: List[Dict],
    collection_name: str
) -> Dict:
    """
    Update multiple objects in a collection using concurrent async operations.
    
    Note: Weaviate does not provide a native 'update_many' method. This implementation
    uses asyncio.gather to execute multiple update operations concurrently, which is
    the recommended approach for batch updates.
    
    For upsert operations (insert or update), consider using upsert_many_objects instead.
    
    Args:
        client: Connected Weaviate async client
        updates: List of dictionaries, each containing 'uuid' and 'properties' keys
                 Example: [
                     {"uuid": "uuid-1", "properties": {"query": "...", "content": "..."}},
                     {"uuid": "uuid-2", "properties": {"query": "...", "content": "..."}}
                 ]
        collection_name: Name of the collection to update
        
    Returns:
        Dict with 'updated_count', 'failed_count', and 'errors' (if any)
    """
    collection = client.collections.get(collection_name)
    
    updated_count = 0
    failed_count = 0
    errors = []
    
    # Process updates concurrently for better performance
    tasks = []
    for update_item in updates:
        if "uuid" not in update_item or "properties" not in update_item:
            failed_count += 1
            errors.append({
                "uuid": update_item.get("uuid"),
                "error": "Missing 'uuid' or 'properties' key in update item"
            })
            continue
        
        task = collection.data.update(
            uuid=update_item["uuid"],
            properties=update_item["properties"]
        )
        tasks.append((update_item["uuid"], task))
    
    # Execute all updates concurrently
    results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
    
    # Process results
    for i, result in enumerate(results):
        uuid = tasks[i][0]
        if isinstance(result, Exception):
            failed_count += 1
            errors.append({
                "uuid": uuid,
                "error": str(result)
            })
        else:
            updated_count += 1
    
    return {
        "updated_count": updated_count,
        "failed_count": failed_count,
        "errors": errors if errors else None,
        "total_processed": len(updates)
    }


async def upsert_many_objects(
    client: weaviate.WeaviateAsyncClient,
    objects: List[Dict],
    collection_name: str
) -> Dict:
    """
    Upsert (insert or update) multiple objects using Weaviate's native batch insert.
    
    This method uses Weaviate's insert_many with explicit UUIDs to perform upserts.
    If an object with the given UUID exists, it will be updated; otherwise, it will be inserted.
    
    This is more efficient than update_many_objects for scenarios where you want to
    insert new objects or update existing ones in a single operation.
    
    Args:
        client: Connected Weaviate async client
        objects: List of dictionaries, each containing 'uuid' and 'properties' keys
                 Example: [
                     {"uuid": "uuid-1", "properties": {"query": "...", "content": "..."}},
                     {"uuid": "uuid-2", "properties": {"query": "...", "content": "..."}}
                 ]
        collection_name: Name of the collection to upsert into
        
    Returns:
        Dict with 'upserted_count', 'failed_count', and 'errors' (if any)
    """
    collection = client.collections.get(collection_name)
    
    # Prepare data objects with UUIDs for insert_many
    data_objects_with_uuids = []
    validation_errors = []
    
    for obj in objects:
        if "uuid" not in obj or "properties" not in obj:
            validation_errors.append({
                "uuid": obj.get("uuid"),
                "error": "Missing 'uuid' or 'properties' key in object"
            })
            continue
        
        # Create data object with UUID for upsert
        from weaviate.classes.data import DataObject
        data_obj = DataObject(
            properties=obj["properties"],
            uuid=obj["uuid"]
        )
        data_objects_with_uuids.append(data_obj)
    
    if not data_objects_with_uuids:
        return {
            "upserted_count": 0,
            "failed_count": len(objects),
            "errors": validation_errors if validation_errors else "No valid objects provided",
            "total_processed": len(objects)
        }
    
    # Use insert_many with UUIDs for upsert behavior
    response = await collection.data.insert_many(data_objects_with_uuids)
    
    # Check for errors in the response
    failed_count = len(validation_errors)
    errors = validation_errors.copy()
    
    if response.has_errors:
        for uuid, error in response.errors.items():
            failed_count += 1
            errors.append({
                "uuid": str(uuid) if uuid else None,
                "error": str(error)
            })
    
    return {
        "upserted_count": len(data_objects_with_uuids) - (failed_count - len(validation_errors)),
        "failed_count": failed_count,
        "errors": errors if errors else None,
        "total_processed": len(objects),
        "all_response": response
    }


async def delete_single_object(
    client: weaviate.WeaviateAsyncClient,
    uuid: str,
    collection_name: str
) -> Dict:
    """
    Delete a single object from a collection using async client.
    
    Args:
        client: Connected Weaviate async client
        uuid: UUID of the object to delete
        collection_name: Name of the collection
        
    Returns:
        Dict with 'uuid', 'success' status, and error if any
    """
    collection = client.collections.get(collection_name)
    
    try:
        # Delete single object
        await collection.data.delete_by_id(uuid=uuid)
        return {
            "uuid": uuid,
            "success": True,
            "error": None
        }
    except Exception as e:
        return {
            "uuid": uuid,
            "success": False,
            "error": str(e)
        }


async def delete_many_objects(
    client: weaviate.WeaviateAsyncClient,
    uuids: List[str],
    collection_name: str
) -> Dict:
    """
    Delete multiple objects from a collection using Weaviate's native batch delete.
    
    This method uses Weaviate's built-in delete_many with Filter.by_id().contains_any()
    which is more efficient than individual deletions.
    
    Args:
        client: Connected Weaviate async client
        uuids: List of UUIDs to delete
        collection_name: Name of the collection
        
    Returns:
        Dict with 'deleted_count', 'failed_count', 'successful' status, and 'errors' (if any)
    """
    collection = client.collections.get(collection_name)
    
    # Filter out empty UUIDs
    valid_uuids = [uuid for uuid in uuids if uuid]
    
    if not valid_uuids:
        return {
            "deleted_count": 0,
            "failed_count": len(uuids),
            "successful": False,
            "errors": "No valid UUIDs provided",
            "total_processed": len(uuids)
        }
    
    try:
        # Use Weaviate's native batch delete with filter
        where_filter = Filter.by_id().contains_any(valid_uuids)
        response = await collection.data.delete_many(where=where_filter)
        
        # Response contains information about the deletion
        deleted_count = response.successful if hasattr(response, 'successful') else len(valid_uuids)
        failed_count = response.failed if hasattr(response, 'failed') else 0
        
        return {
            "deleted_count": deleted_count,
            "failed_count": failed_count,
            "successful": response.successful > 0 if hasattr(response, 'successful') else True,
            "errors": None,
            "total_processed": len(uuids),
            "response": response
        }
    except Exception as e:
        return {
            "deleted_count": 0,
            "failed_count": len(uuids),
            "successful": False,
            "errors": str(e),
            "total_processed": len(uuids)
        }


async def get_object_by_uuid(
    client: weaviate.WeaviateAsyncClient,
    uuid: str,
    collection_name: str,
    return_properties: Optional[List[str]] = None
) -> Dict:
    """
    Retrieve a single object by UUID from a collection using async client.
    
    Args:
        client: Connected Weaviate async client
        uuid: UUID of the object to retrieve
        collection_name: Name of the collection
        return_properties: Optional list of properties to return. If None, returns all properties.
        
    Returns:
        Dict with 'uuid', 'properties', 'success' status, and error if any
    """
    collection = client.collections.get(collection_name)
    
    try:
        # Fetch object by UUID
        obj = await collection.query.fetch_object_by_id(
            uuid=uuid,
            return_properties=return_properties
        )
        
        if obj is None:
            return {
                "uuid": uuid,
                "properties": None,
                "success": False,
                "error": "Object not found"
            }
        
        return {
            "uuid": str(obj.uuid),
            "properties": obj.properties,
            "success": True,
            "error": None
        }
    except Exception as e:
        return {
            "uuid": uuid,
            "properties": None,
            "success": False,
            "error": str(e)
        }


async def get_objects_by_uuids(
    client: weaviate.WeaviateAsyncClient,
    uuids: List[str],
    collection_name: str,
    return_properties: Optional[List[str]] = None
) -> Dict:
    """
    Retrieve multiple objects by UUIDs from a collection using Weaviate's native batch fetch.
    
    This method uses Weaviate's built-in fetch_objects with Filter.by_id().contains_any()
    which is more efficient than individual fetches.
    
    Args:
        client: Connected Weaviate async client
        uuids: List of UUIDs to retrieve
        collection_name: Name of the collection
        return_properties: Optional list of properties to return. If None, returns all properties.
        
    Returns:
        Dict with 'objects', 'found_count', 'not_found_count', and 'errors' (if any)
    """
    collection = client.collections.get(collection_name)
    
    # Filter out empty UUIDs
    valid_uuids = [uuid for uuid in uuids if uuid]
    
    if not valid_uuids:
        return {
            "objects": [],
            "found_count": 0,
            "not_found_count": len(uuids),
            "errors": "No valid UUIDs provided",
            "total_processed": len(uuids)
        }
    
    try:
        # Use Weaviate's native batch fetch with filter
        where_filter = Filter.by_id().contains_any(valid_uuids)
        response = await collection.query.fetch_objects(
            where=where_filter,
            return_properties=return_properties
        )
        
        # Extract objects from response
        objects = []
        for obj in response.objects:
            objects.append({
                "uuid": str(obj.uuid),
                "properties": obj.properties
            })
        
        found_count = len(objects)
        not_found_count = len(valid_uuids) - found_count
        
        # Identify which UUIDs were not found
        found_uuids = {str(obj.uuid) for obj in response.objects}
        missing_uuids = [uuid for uuid in valid_uuids if uuid not in found_uuids]
        
        errors = None
        if missing_uuids:
            errors = [{"uuid": uuid, "error": "Object not found"} for uuid in missing_uuids]
        
        return {
            "objects": objects,
            "found_count": found_count,
            "not_found_count": not_found_count,
            "errors": errors,
            "total_processed": len(uuids)
        }
    except Exception as e:
        return {
            "objects": [],
            "found_count": 0,
            "not_found_count": len(uuids),
            "errors": str(e),
            "total_processed": len(uuids)
        }


async def semantic_search(
    client: weaviate.WeaviateAsyncClient, 
    query_text: str, 
    collection_name: str,
    limit: int = 3,
    return_properties: Optional[List[str]] = None
) -> List[Dict]:

    collection = client.collections.get(collection_name)
    
    response = await collection.query.near_text(
        query=query_text,
        limit=limit,
        return_metadata=wvc.query.MetadataQuery(distance=True, score=True)
    )
    
    results = []
    for i, obj in enumerate(response.objects, 1):
        result = {
            "rank": i,
            "uuid": obj.uuid,
            "customer_query": obj.properties.get('customer_query', ''),
            "agent_responses": obj.properties.get('agent_responses', {}),
            "scenario": obj.properties.get('scenario', ''),
            "distance": obj.metadata.distance if hasattr(obj.metadata, 'distance') else None,
            "score": obj.metadata.score if hasattr(obj.metadata, 'score') else None
        }
        results.append(result)
    
    return results


async def hybrid_search(
    client: weaviate.WeaviateAsyncClient,
    query_text: str,
    collection_name: str,
    limit: int = 3,
    alpha: float = 0.5,
    return_properties: Optional[List[str]] = None
) -> List[Dict]:


    collection = client.collections.get(collection_name)
    
    response = await collection.query.hybrid(
        query=query_text,
        limit=limit,
        alpha=alpha,
        return_metadata=wvc.query.MetadataQuery(score=True, explain_score=True)
    )
    
    results = []
    for i, obj in enumerate(response.objects, 1):
        result = {
            "rank": i,
            "uuid": obj.uuid,
            "customer_query": obj.properties.get('customer_query', ''),
            "agent_responses": obj.properties.get('agent_responses', {}),
            "scenario": obj.properties.get('scenario', ''),
            "score": obj.metadata.score if hasattr(obj.metadata, 'score') else None,
            "explain_score": obj.metadata.explain_score if hasattr(obj.metadata, 'explain_score') else None
        }
        results.append(result)
    
    return results


async def search(
    client: weaviate.WeaviateAsyncClient,
    query_text: str,
    collection_name: str,
    limit: int = 3,
    search_type: Literal["semantic", "hybrid"] = "hybrid",
    alpha: float = 0.5,
    return_properties: Optional[List[str]] = None
) -> List[Dict]:

    if search_type == "semantic":
        return await semantic_search(client, query_text, collection_name, limit, return_properties)
    elif search_type == "hybrid":
        return await hybrid_search(client, query_text, collection_name, limit, alpha, return_properties)
    else:
        raise ValueError(f"Invalid search_type: {search_type}. Must be 'semantic' or 'hybrid'")


async def get_collection_stats(
    client: weaviate.WeaviateAsyncClient,
    collection_name: str
) -> Dict:
    """
    Get statistics for a collection.
    
    Args:
        client: Connected Weaviate async client
        collection_name: Name of the collection
        
    Returns:
        Dict with collection name and total count
        
    Raises:
        ValueError: If the collection doesn't exist
    """
    # Check if collection exists first
    exists = await collection_exists(client, collection_name)
    if not exists:
        raise ValueError(
            f"Collection '{collection_name}' does not exist. "
            f"Please create the collection first with proper vectorizer configuration using create_collection()."
        )

    collection = client.collections.get(collection_name)
    response = await collection.aggregate.over_all(total_count=True)
    
    return {
        "collection_name": collection_name,
        "total_count": response.total_count
    }


async def collection_exists(
    client: weaviate.WeaviateAsyncClient,
    collection_name: str
) -> bool:

    try:
        return await client.collections.exists(collection_name)
    except Exception:
        return False


async def list_collections(client: weaviate.WeaviateAsyncClient) -> List[str]:

    collections = await client.collections.list_all()
    return [collection.name for collection in collections.values()]
