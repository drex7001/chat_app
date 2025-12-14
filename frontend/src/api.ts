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

export default api;
