import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000',
    headers: {
        'Content-Type': 'application/json',
    },
});

export const getClients = async () => {
    const response = await api.get('/clients/');
    return response.data;
};

export const getClient = async (id: number) => {
    const response = await api.get(`/clients/${id}`);
    return response.data;
};

export const createClient = async (data: any) => {
    const response = await api.post('/clients/', data);
    return response.data;
};

export const updateClient = async (id: number, data: any) => {
    const response = await api.patch(`/clients/${id}`, data);
    return response.data;
};

// --- New Product Methods ---

export const getProducts = async (clientId: number, storeId?: number, cursor?: string) => {
    const params: any = {};
    if (storeId) params.store_id = storeId;
    if (cursor) params.cursor = cursor;

    const response = await api.get(`/api/v1/${clientId}/products`, { params });
    return response.data;
};

export const triggerSync = async (clientId: number, storeId?: number, limit: number = 50, freshStart: boolean = false) => {
    let url = `/api/v1/${clientId}/products/sync?limit=${limit}&fresh_start=${freshStart}`;
    if (storeId) {
        url += `&store_id=${storeId}`;
    }
    const response = await api.post(url);
    return response.data;
};

export const triggerProductSync = async (clientId: number, productId: number, storeId: number) => {
    const response = await api.post(`/api/v1/${clientId}/products/${productId}/sync?store_id=${storeId}`);
    return response.data;
};

export const getProductSyncStatus = async (clientId: number, productId: number) => {
    const response = await api.get(`/api/v1/${clientId}/products/${productId}/sync-status`);
    return response.data; // { product_id, vector_count, is_synced }
};

export const searchProducts = async (clientId: number, imageUrl: string) => {
    const response = await api.post(`/api/v1/${clientId}/search`, { image_url: imageUrl });
    return response.data;
};

// --- Chat & Uploads ---

export const uploadFile = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/v1/uploads/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data; // { url, filename, content_type }
};

export const sendMessage = async (payload: {
    message_id: string;
    thread_id: string;
    client_external_id: string;
    text: string;
    attachments?: { url: string; type: string }[];
    app_name?: string;
    sender_type?: string;
}) => {
    const response = await api.post('/ai/message', payload);
    return response.data;
};

export default api;
