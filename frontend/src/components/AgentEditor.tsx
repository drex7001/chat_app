import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import type { AgentConfig } from '../types';

interface AgentEditorProps {
    agentKey: string;
    initialData?: AgentConfig;
    onSave: (key: string, data: AgentConfig) => void;
    onCancel: () => void;
}

const DEFAULT_AGENT: AgentConfig = {
    name: '',
    role: 'specialist',
    model: 'gpt-4o-mini',
    instructions: '',
    tools: []
};

const AgentEditor: React.FC<AgentEditorProps> = ({ agentKey, initialData, onSave, onCancel }) => {
    const [data, setData] = useState<AgentConfig>(initialData || DEFAULT_AGENT);
    const [key, setKey] = useState(agentKey);

    useEffect(() => {
        if (initialData) setData(initialData);
        setKey(agentKey);
    }, [initialData, agentKey]);

    return (
        <Card className="border-2 border-blue-100 shadow-lg">
            <CardHeader>
                <CardTitle>{initialData ? 'Edit Agent' : 'New Agent'}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label>Agent ID (Key)</Label>
                        <Input
                            value={key}
                            onChange={e => setKey(e.target.value)}
                            disabled={!!initialData && key === 'orchestrator'} // Lock orchestrator key
                            placeholder="e.g. sales_agent"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label>Display Name</Label>
                        <Input
                            value={data.name}
                            onChange={e => setData({ ...data, name: e.target.value })}
                            placeholder="e.g. Sales Assistant"
                        />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <Label>Role</Label>
                        <Input
                            value={data.role}
                            onChange={e => setData({ ...data, role: e.target.value })}
                            placeholder="orchestrator | specialist"
                        />
                    </div>
                    <div className="space-y-2">
                        <Label>Model</Label>
                        <Input
                            value={data.model}
                            onChange={e => setData({ ...data, model: e.target.value })}
                            placeholder="gpt-4o-mini"
                        />
                    </div>
                </div>

                <div className="space-y-2">
                    <Label>System Instructions</Label>
                    <Textarea
                        className="min-h-[200px] font-mono text-sm"
                        value={data.instructions}
                        onChange={e => setData({ ...data, instructions: e.target.value })}
                        placeholder="You are a helpful assistant..."
                    />
                </div>
            </CardContent>
            <CardFooter className="flex justify-between">
                <Button variant="outline" onClick={onCancel}>Cancel</Button>
                <Button onClick={() => onSave(key, data)}>Save Agent</Button>
            </CardFooter>
        </Card>
    );
};

export default AgentEditor;
