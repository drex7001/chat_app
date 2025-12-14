import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, Edit, Server } from 'lucide-react';
import { getClients } from '../api';
import type { Client } from '../types';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

const ClientList: React.FC = () => {
    const [clients, setClients] = useState<Client[]>([]);

    useEffect(() => {
        loadClients();
    }, []);

    const loadClients = async () => {
        try {
            const data = await getClients();
            setClients(data);
        } catch (error) {
            console.error('Failed to load clients', error);
        }
    };

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-8">
            <div className="flex justify-between items-center">
                <div className="space-y-1">
                    <h1 className="text-3xl font-bold tracking-tight text-gray-900">Agent Orchestration</h1>
                    <p className="text-gray-500">Manage companies, agents, and policies.</p>
                </div>
                <Link to="/new">
                    <Button>
                        <Plus className="mr-2 h-4 w-4" /> Add Company
                    </Button>
                </Link>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>Companies</CardTitle>
                    <CardDescription>List of all companies utilizing the agent system.</CardDescription>
                </CardHeader>
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Company Name</TableHead>
                                <TableHead>App ID</TableHead>
                                <TableHead>Created At</TableHead>
                                <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {clients.map((client) => (
                                <TableRow key={client.id}>
                                    <TableCell className="font-medium flex items-center gap-2">
                                        <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
                                            <Server size={16} />
                                        </div>
                                        {client.name}
                                    </TableCell>
                                    <TableCell>
                                        <Badge variant="outline" className="font-mono">{client.external_id}</Badge>
                                    </TableCell>
                                    <TableCell className="text-gray-500 text-sm">
                                        {new Date(client.created_at).toLocaleDateString()}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Link to={`/client/${client.id}`}>
                                            <Button variant="ghost" size="sm">
                                                <Edit className="mr-2 h-4 w-4" /> Manage
                                            </Button>
                                        </Link>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>
        </div>
    );
};

export default ClientList;
