export interface AgentConfig {
    name: string;
    role: string;
    instructions: string;
    model: string;
    tools: string[];
}

export interface PolicyDocument {
    name: string;
    content: string;
}

export interface PolicyConfig {
    documents: PolicyDocument[];
    rules: Record<string, any>;
}

export interface ClientConfig {
    agents: Record<string, AgentConfig>;
}

export interface Client {
    id: number;
    external_id: string;
    name: string;
    config: ClientConfig;
    policies: PolicyConfig;
    created_at: string;
    updated_at: string;
}

export interface ClientCreate {
    name: string;
    external_id: string;
    config?: Partial<ClientConfig>;
    policies?: Partial<PolicyConfig>;
}

export interface ClientUpdate {
    name?: string;
    config?: Partial<ClientConfig>;
    policies?: Partial<PolicyConfig>;
}
