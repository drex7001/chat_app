import React, { useState, useEffect } from 'react';
import { getProducts, triggerSync, searchProducts, triggerProductSync, getProductSyncStatus } from '../api';
import { toast } from 'sonner';

interface Product {
    id: number;
    title: string;
    status: string;
    images: { src: string; id: number }[];
    variants: { price: string }[];
}

interface ProductListProps {
    clientId: number;
}

const ProductList: React.FC<ProductListProps> = ({ clientId }) => {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(false);
    const [storeId, setStoreId] = useState<number | undefined>(undefined);
    const [cursor] = useState<string | undefined>(undefined);
    const [searchUrl, setSearchUrl] = useState('');

    const [availableStores, setAvailableStores] = useState<{ id: number, name: string }[]>([]);
    const [invalidStores, setInvalidStores] = useState<{ id: number, name: string, error: string }[]>([]);
    const [apiError, setApiError] = useState<string | null>(null);
    const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
    const [selectedImageIndex, setSelectedImageIndex] = useState(0);
    const [syncStatus, setSyncStatus] = useState<{ is_synced: boolean, vector_count: number } | null>(null);

    // For demo store selector (in real app, fetch stores from API)
    // We can infer stores from the product response metadata if available, 
    // or need a separate /stores endpoint. 
    // Using simple number input for Store ID for Phase 1.

    const loadProducts = async () => {
        setLoading(true);
        setApiError(null);
        try {
            const data = await getProducts(clientId, storeId, cursor);
            setProducts(data.products || []);

            // Handle available stores
            if (data.available_stores) {
                setAvailableStores(data.available_stores);
                if (!storeId && data.available_stores.length > 0) {
                    setStoreId(data.store_id);
                }
            }

            // Handle invalid stores - show warning
            if (data.invalid_stores?.length > 0) {
                setInvalidStores(data.invalid_stores);
                toast.warning(`${data.invalid_stores.length} store(s) have invalid credentials`);
            } else {
                setInvalidStores([]);
            }

            // Handle API-level error (e.g., all stores invalid)
            if (data.error) {
                setApiError(data.error);
                toast.error(data.error);
            }
        } catch (error) {
            toast.error("Failed to load products");
            console.error(error);
        } finally {
            setLoading(false);
        }
    };

    const handleSync = async (specificStoreId?: number, limit: number = 50) => {
        try {
            await triggerSync(clientId, specificStoreId, limit, false);
            toast.success(specificStoreId ? `Syncing store (limit ${limit})...` : "Syncing all...");
        } catch (error) {
            toast.error("Failed to trigger sync");
        }
    };

    const handleProductSync = async () => {
        if (!selectedProduct || !storeId) return;
        try {
            await triggerProductSync(clientId, selectedProduct.id, storeId);
            toast.success(`Sync started for ${selectedProduct.title}`);
            // Re-check status after a delay
            setTimeout(() => checkStatus(selectedProduct.id), 2000);
        } catch (error) {
            toast.error("Failed to sync product");
        }
    };

    const handleResetSync = async () => {
        if (!confirm("This will DELETE ALL existing vector data and rebuild the database with the new SKU schema. Are you sure?")) return;
        try {
            // Trigger Reset with limit 50 (or small number) for the selected store or all? 
            // For safety, let's sync the selected store or just trigger the reset.
            // Using storeId if selected, else undefined (Global Reset + Sync 50)
            await triggerSync(clientId, storeId, 50, true);
            toast.success("Database Reset & Sync started!");
        } catch (error) {
            toast.error("Failed to reset database");
        }
    };

    const handleSearch = async () => {
        if (!searchUrl) return;
        setLoading(true);
        try {
            const results = await searchProducts(clientId, searchUrl);
            toast.success(`Found ${results.length} matches`);
            // TODO: Display search results
            // specific to phase 1, just logging or simple alert
            console.log(results);
        } catch (error) {
            toast.error("Search failed");
        } finally {
            setLoading(false);
        }
    };

    const checkStatus = async (pid: number) => {
        setSyncStatus(null);
        try {
            const status = await getProductSyncStatus(clientId, pid);
            setSyncStatus(status);
        } catch (e) {
            console.error("Failed to check status", e);
        }
    };

    useEffect(() => {
        loadProducts();
    }, [clientId, storeId, cursor]);

    // Reset image index when product changes
    useEffect(() => {
        if (selectedProduct) {
            setSelectedImageIndex(0);
            checkStatus(selectedProduct.id);
        } else {
            setSyncStatus(null);
        }
    }, [selectedProduct]);

    return (
        <div className="p-6 space-y-6 max-w-7xl mx-auto">
            {/* Header Section */}
            <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 flex flex-col md:flex-row justify-between items-center gap-4">
                <div className="flex items-center gap-4 w-full md:w-auto">
                    <h2 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-purple-600">
                        Products
                    </h2>

                    {/* Store Selector */}
                    <div className="flex items-center gap-2 flex-1 md:flex-none">
                        <select
                            className="bg-gray-50 border border-gray-200 text-gray-700 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5"
                            value={storeId || ''}
                            onChange={(e) => setStoreId(parseInt(e.target.value))}
                        >
                            <option value="">Select Store...</option>
                            {availableStores.map(store => (
                                <option key={store.id} value={store.id}>
                                    {store.name} ({store.id})
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-2 w-full md:w-auto justify-end items-center">
                    <div className="flex items-center gap-2 border rounded-lg px-2 bg-gray-50">
                        <input
                            type="text"
                            placeholder="Image URL..."
                            className="bg-transparent border-none focus:ring-0 text-sm w-32 md:w-48"
                            value={searchUrl}
                            onChange={(e) => setSearchUrl(e.target.value)}
                        />
                        <button
                            onClick={handleSearch}
                            className="text-gray-500 hover:text-blue-600 p-1"
                            title="Search by URL"
                        >
                            🔍
                        </button>
                    </div>
                    <button
                        onClick={() => handleSync(storeId, 50)}
                        className="bg-emerald-500 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 shadow-sm shadow-emerald-200"
                        disabled={!storeId}
                    >
                        Sync Store
                    </button>
                    <button
                        onClick={handleResetSync}
                        className="bg-white border border-red-200 text-red-600 hover:bg-red-50 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                        title="Wipes DB and re-syncs everything"
                    >
                        Reset DB
                    </button>
                    <button
                        onClick={loadProducts}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-md shadow-blue-200 transition-colors"
                    >
                        Refresh
                    </button>
                </div>
            </div>

            {/* Product Grid */}
            {loading ? (
                <div className="flex justify-center items-center py-20">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-6">
                    {products.map((p) => (
                        <div
                            key={p.id}
                            onClick={() => setSelectedProduct(p)}
                            className="group bg-white rounded-xl border border-gray-100 overflow-hidden hover:shadow-xl hover:translate-y-[-2px] transition-all cursor-pointer relative"
                        >
                            <div className="aspect-[3/4] bg-gray-50 relative overflow-hidden">
                                {p.images?.[0]?.src ? (
                                    <img
                                        src={p.images[0].src}
                                        alt={p.title}
                                        className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500"
                                    />
                                ) : (
                                    <div className="w-full h-full flex items-center justify-center text-gray-300">
                                        No Image
                                    </div>
                                )}
                                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded-full shadow-sm ${p.status === 'active' ? 'bg-white/90 text-emerald-700' : 'bg-gray-100 text-gray-600'
                                        }`}>
                                        {p.status}
                                    </span>
                                </div>
                                {/* Image Count Badge */}
                                {p.images.length > 1 && (
                                    <div className="absolute bottom-2 right-2 bg-black/50 text-white text-[10px] px-2 py-1 rounded-full">
                                        +{p.images.length - 1}
                                    </div>
                                )}
                            </div>
                            <div className="p-4">
                                <h3 className="font-semibold text-gray-900 truncate text-sm leading-tight mb-1">{p.title}</h3>
                                <p className="text-gray-500 text-xs font-medium">
                                    {p.variants?.[0]?.price ? `$${p.variants[0].price}` : 'N/A'}
                                </p>
                            </div>
                        </div>
                    ))}
                    {products.length === 0 && (
                        <div className="col-span-full py-12 text-center bg-gray-50 rounded-xl border border-dashed space-y-4">
                            {apiError ? (
                                <div className="text-red-600 font-medium">
                                    <span className="text-2xl">⚠️</span>
                                    <p className="mt-2">{apiError}</p>
                                </div>
                            ) : (
                                <p className="text-gray-400">No products found. Select a store or sync.</p>
                            )}

                            {invalidStores.length > 0 && (
                                <div className="mt-4 text-sm text-amber-700 bg-amber-50 rounded-lg p-4 mx-auto max-w-md">
                                    <p className="font-semibold mb-2">⚠️ Stores with invalid credentials:</p>
                                    <ul className="text-left space-y-1">
                                        {invalidStores.map(store => (
                                            <li key={store.id}>• {store.name}: {store.error}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* Product Detail Modal */}
            {selectedProduct && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={() => setSelectedProduct(null)}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col md:flex-row" onClick={e => e.stopPropagation()}>

                        {/* Image Section (Gallery) */}
                        <div className="w-full md:w-1/2 bg-gray-100 flex flex-col">
                            {/* Main Image */}
                            <div className="flex-1 flex items-center justify-center p-4 overflow-hidden relative">
                                {selectedProduct.images?.[selectedImageIndex]?.src ? (
                                    <img
                                        src={selectedProduct.images[selectedImageIndex].src}
                                        className="max-h-full max-w-full object-contain shadow-sm"
                                    />
                                ) : (
                                    <div className="text-gray-400">No Image</div>
                                )}
                            </div>

                            {/* Thumbnails */}
                            {selectedProduct.images && selectedProduct.images.length > 1 && (
                                <div className="h-20 bg-white border-t flex gap-2 p-2 overflow-x-auto">
                                    {selectedProduct.images.map((img, idx) => (
                                        <button
                                            key={img.id || idx}
                                            onClick={() => setSelectedImageIndex(idx)}
                                            className={`flex-shrink-0 w-16 h-16 border rounded overflow-hidden ${selectedImageIndex === idx ? 'ring-2 ring-blue-500 border-transparent' : 'border-gray-200'}`}
                                        >
                                            <img src={img.src} className="w-full h-full object-cover" />
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Details Section */}
                        <div className="w-full md:w-1/2 p-8 flex flex-col overflow-y-auto">
                            <div className="flex justify-between items-start mb-6">
                                <div>
                                    <h2 className="text-2xl font-bold text-gray-900 mb-2">{selectedProduct.title}</h2>
                                    <div className="flex items-center gap-3">
                                        <span className="text-xl font-medium text-blue-600">
                                            {selectedProduct.variants?.[0]?.price ? `$${selectedProduct.variants[0].price}` : 'N/A'}
                                        </span>
                                        <span className={`px-2 py-1 text-xs font-bold uppercase rounded-md ${selectedProduct.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-600'
                                            }`}>
                                            {selectedProduct.status}
                                        </span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setSelectedProduct(null)}
                                    className="p-2 hover:bg-gray-100 rounded-full text-gray-500"
                                >
                                    ✕
                                </button>
                            </div>

                            <div className="space-y-4 flex-1">
                                <div className="bg-gray-50 p-4 rounded-lg border text-sm text-gray-600 space-y-2">
                                    <p><span className="font-semibold text-gray-800">Product ID:</span> {selectedProduct.id}</p>
                                    <p><span className="font-semibold text-gray-800">Total Variants:</span> {selectedProduct.variants?.length || 0}</p>
                                    <p><span className="font-semibold text-gray-800">Total Images:</span> {selectedProduct.images?.length || 0}</p>
                                    <p><span className="font-semibold text-gray-800">Store ID:</span> {storeId}</p>
                                </div>

                                <div className={`p-4 rounded-lg border text-sm ${syncStatus?.is_synced
                                    ? 'bg-emerald-50 border-emerald-100 text-emerald-800'
                                    : 'bg-amber-50 border-amber-100 text-amber-800'
                                    }`}>
                                    <p className="font-bold flex items-center gap-2">
                                        {syncStatus ? (
                                            syncStatus.is_synced
                                                ? <span>✅ Synced to Milvus ({syncStatus.vector_count} vectors)</span>
                                                : <span>⚠️ Not Synced to Milvus</span>
                                        ) : (
                                            <span>⏳ Checking Sync Status...</span>
                                        )}
                                    </p>
                                    {!syncStatus?.is_synced && (
                                        <p className="mt-1 opacity-90">
                                            This product is missing from vector search. Click "Sync" below to fix.
                                        </p>
                                    )}
                                </div>
                            </div>

                            <div className="mt-8 pt-6 border-t flex flex-col gap-3">
                                <button
                                    onClick={handleProductSync}
                                    className="w-full bg-purple-600 hover:bg-purple-700 text-white py-3 rounded-xl font-medium transition-colors shadow-md shadow-purple-100 flex items-center justify-center gap-2"
                                >
                                    <span>⚡</span> Sync This Product to Milvus
                                </button>

                                <div className="flex gap-3">
                                    <button
                                        className="flex-1 bg-gray-100 hover:bg-gray-200 text-gray-700 py-3 rounded-xl font-medium transition-colors"
                                        onClick={() => confirm("JSON Data:\n" + JSON.stringify(selectedProduct, null, 2))}
                                    >
                                        View Raw JSON
                                    </button>
                                    {/* Link requires store URL, which we don't have in Product list directly yet without iterating stores. 
                                        Assuming dynamic URL or we can fetch it. For now, disable or generic.
                                    */}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ProductList;
