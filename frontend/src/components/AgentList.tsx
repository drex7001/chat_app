import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Plus, Edit, Bot, Trash2 } from 'lucide-react';
import type { AgentConfig } from '../types';

interface AgentListProps {
    agents: Record<string, AgentConfig>;
    onEdit: (key: string) => void;
    onDelete: (key: string) => void;
    onAdd: () => void;
}

const AgentList: React.FC<AgentListProps> = ({ agents, onEdit, onDelete, onAdd }) => {
    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <div>
                    <CardTitle>Agents</CardTitle>
                    <CardDescription>Manage the specialized agents for this client.</CardDescription>
                </div>
                <Button onClick={onAdd} size="sm" className="gap-2">
                    <Plus size={16} /> Add Agent
                </Button>
            </CardHeader>
            <CardContent>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Agent Name</TableHead>
                            <TableHead>Role</TableHead>
                            <TableHead>Model</TableHead>
                            <TableHead className="w-[100px]">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {agents && Object.entries(agents).map(([key, agent]) => (
                            <TableRow key={key}>
                                <TableCell className="font-medium flex items-center gap-2">
                                    <Bot size={16} className="text-blue-500" />
                                    {agent.name}
                                    {key === 'orchestrator' && <Badge variant="secondary" className="text-xs">Main</Badge>}
                                </TableCell>
                                <TableCell>{agent.role}</TableCell>
                                <TableCell className="font-mono text-xs">{agent.model}</TableCell>
                                <TableCell>
                                    <div className="flex gap-2">
                                        <Button variant="ghost" size="icon" onClick={() => onEdit(key)}>
                                            <Edit size={16} />
                                        </Button>
                                        <Button variant="ghost" size="icon" onClick={() => onDelete(key)} className="text-red-500 hover:text-red-600 hover:bg-red-50">
                                            <Trash2 size={16} />
                                        </Button>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
};

export default AgentList;
