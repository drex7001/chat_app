import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, Save, Plus, Trash2 } from 'lucide-react';
import { getClient, createClient, updateClient } from '../api';
import type { Client, ClientConfig, PolicyConfig, AgentConfig, PolicyDocument } from '../types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { toast } from "sonner"
import AgentList from './AgentList';
import AgentEditor from './AgentEditor';

const DEFAULT_CONFIG: ClientConfig = { agents: {} };
const DEFAULT_POLICIES: PolicyConfig = { documents: [], rules: {} };

const ClientEditor: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const isNew = !id;

    // State
    const [name, setName] = useState('');
    const [externalId, setExternalId] = useState('');
    const [config, setConfig] = useState<ClientConfig>(DEFAULT_CONFIG);
    const [policies, setPolicies] = useState<PolicyConfig>(DEFAULT_POLICIES);

    // Agent Editing State
    const [editingAgentKey, setEditingAgentKey] = useState<string | null>(null);
    const [isAgentModalOpen, setIsAgentModalOpen] = useState(false);

    useEffect(() => {
        if (!isNew && id) {
            loadClient(parseInt(id));
        }
    }, [id, isNew]);

    const loadClient = async (clientId: number) => {
        try {
            const data: Client = await getClient(clientId);
            setName(data.name);
            setExternalId(data.external_id);
            const clientConfig = data.config || DEFAULT_CONFIG;
            if (!clientConfig.agents) {
                clientConfig.agents = {};
            }
            setConfig(clientConfig);
            setPolicies(data.policies || DEFAULT_POLICIES);
        } catch (error) {
            console.error('Failed to load client', error);
        }
    };

    const handleSave = async () => {
        try {
            const payload = {
                name,
                external_id: externalId, // Only used for create, but doesn't hurt to pass? No, API might reject if not in schema for Update.
                config,
                policies
            };

            if (isNew) {
                await createClient(payload);
            } else {
                await updateClient(parseInt(id!), { name, config, policies });
            }
            navigate('/');
            toast.success("Client saved successfully");
        } catch (error) {
            console.error('Failed to save', error);
            toast.error("Failed to save client");
        }
    };

    // --- Agent Handlers ---
    const handleAddAgent = () => {
        setEditingAgentKey(null);
        setIsAgentModalOpen(true);
    };

    const handleEditAgent = (key: string) => {
        setEditingAgentKey(key);
        setIsAgentModalOpen(true);
    };

    const handleSaveAgent = async (key: string, agentData: AgentConfig) => {
        if (!key.trim()) {
            toast.error("Agent ID cannot be empty");
            return;
        }

        const newAgents = { ...(config.agents || {}) };

        // If key changed (renamed), delete old key
        if (editingAgentKey && editingAgentKey !== key) {
            delete newAgents[editingAgentKey];
        }

        newAgents[key] = agentData;
        const newConfig = { ...config, agents: newAgents };

        // Update local state
        setConfig(newConfig);
        setIsAgentModalOpen(false);

        // Auto-save to backend
        try {
            await updateClient(parseInt(id!), { name, config: newConfig, policies });
            toast.success("Agent saved successfully");
        } catch (error) {
            console.error('Failed to save agent', error);
            toast.error("Failed to save agent");
        }
    };

    const handleDeleteAgent = async (key: string) => {
        if (!window.confirm(`Are you sure you want to delete agent "${key}"?`)) {
            return;
        }

        const newAgents = { ...(config.agents || {}) };
        delete newAgents[key];
        const newConfig = { ...config, agents: newAgents };

        setConfig(newConfig);

        try {
            await updateClient(parseInt(id!), { name, config: newConfig, policies });
            toast.success("Agent deleted successfully");
        } catch (error) {
            console.error('Failed to delete agent', error);
            toast.error("Failed to delete agent");
            // Revert on failure (optional but good practice)
            loadClient(parseInt(id!));
        }
    };

    // --- Policy Handlers ---
    const handleAddDocument = () => {
        setPolicies({
            ...policies,
            documents: [...policies.documents, { name: 'New Policy', content: '' }]
        });
    };

    const updateDocument = (index: number, field: keyof PolicyDocument, value: string) => {
        const newDocs = [...policies.documents];
        newDocs[index] = { ...newDocs[index], [field]: value };
        setPolicies({ ...policies, documents: newDocs });
    };

    const removeDocument = (index: number) => {
        const newDocs = policies.documents.filter((_, i) => i !== index);
        setPolicies({ ...policies, documents: newDocs });
    };

    return (
        <div className="p-8 max-w-6xl mx-auto space-y-8">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link to="/">
                        <Button variant="outline" size="icon">
                            <ArrowLeft size={16} />
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight">{isNew ? 'New Company' : name}</h1>
                        <p className="text-gray-500">{isNew ? 'Onboard a new client' : `Managing ${name} (${externalId})`}</p>
                    </div>
                </div>
                <Button onClick={handleSave}>
                    <Save className="mr-2 h-4 w-4" /> Save Changes
                </Button>
            </div>

            {/* Main Content */}
            <Tabs defaultValue="details" className="space-y-4">
                <TabsList>
                    <TabsTrigger value="details">Details</TabsTrigger>
                    <TabsTrigger value="agents">Agents</TabsTrigger>
                    <TabsTrigger value="policies">Policies</TabsTrigger>
                </TabsList>

                {/* Details Tab */}
                <TabsContent value="details">
                    <Card>
                        <CardHeader>
                            <CardTitle>Company Details</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Company Name</Label>
                                    <Input value={name} onChange={e => setName(e.target.value)} />
                                </div>
                                <div className="space-y-2">
                                    <Label>App ID (External ID)</Label>
                                    <Input value={externalId} onChange={e => setExternalId(e.target.value)} disabled={!isNew} />
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Agents Tab */}
                <TabsContent value="agents">
                    <div className="space-y-4">
                        <AgentList
                            agents={config.agents}
                            onEdit={handleEditAgent}
                            onDelete={handleDeleteAgent}
                            onAdd={handleAddAgent}
                        />
                    </div>
                </TabsContent>

                {/* Policies Tab */}
                <TabsContent value="policies">
                    <Card>
                        <CardHeader>
                            <CardTitle>Policy Documents</CardTitle>
                            <CardDescription>Knowledge base documents for the agents.</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {policies.documents.map((doc, idx) => (
                                <Card key={idx} className="border border-gray-200">
                                    <CardContent className="pt-6 space-y-4">
                                        <div className="flex gap-4">
                                            <div className="flex-1 space-y-2">
                                                <Label>Document Name</Label>
                                                <Input value={doc.name} onChange={e => updateDocument(idx, 'name', e.target.value)} />
                                            </div>
                                            <Button variant="destructive" size="icon" onClick={() => removeDocument(idx)} className="mt-8">
                                                <Trash2 size={16} />
                                            </Button>
                                        </div>
                                        <div className="space-y-2">
                                            <Label>Content</Label>
                                            <Textarea
                                                value={doc.content}
                                                onChange={e => updateDocument(idx, 'content', e.target.value)}
                                                className="min-h-[150px]"
                                            />
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                            <Button variant="outline" onClick={handleAddDocument} className="w-full">
                                <Plus className="mr-2 h-4 w-4" /> Add Document
                            </Button>
                        </CardContent>
                    </Card>

                    <Card className="mt-4">
                        <CardHeader>
                            <CardTitle>Machine Rules</CardTitle>
                            <CardDescription>JSON configuration for deterministic rules.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Textarea
                                className="font-mono min-h-[150px]"
                                value={JSON.stringify(policies.rules, null, 2)}
                                onChange={e => {
                                    try {
                                        const parsed = JSON.parse(e.target.value);
                                        setPolicies({ ...policies, rules: parsed });
                                    } catch (err) {
                                        // ignore
                                    }
                                }}
                            />
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* Agent Editor Overlay */}
            {isAgentModalOpen && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 overflow-y-auto">
                    <div className="w-full max-w-2xl bg-white rounded-lg shadow-xl">
                        <AgentEditor
                            agentKey={editingAgentKey || ''}
                            initialData={editingAgentKey ? config.agents[editingAgentKey] : undefined}
                            onSave={handleSaveAgent}
                            onCancel={() => setIsAgentModalOpen(false)}
                        />
                    </div>
                </div>
            )}
        </div>
    );
};

export default ClientEditor;
