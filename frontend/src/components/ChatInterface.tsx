import React, { useState, useEffect, useRef } from 'react';
import { Send, Mic, Paperclip, X, Image as ImageIcon, Loader2 } from 'lucide-react';
import { getClients, sendMessage, uploadFile, transcribeAudio } from '../api';
// If UI components don't exist, I'll use standard HTML/Tailwind for now to avoid specific lib dependency issues if not fully set up.
// Actually, package.json has @radix-ui, so likely shadcn. I'll stick to raw tailwind for speed/stability unless I see the components dir.
// I saw components/ui dir earlier.

interface Message {
    id: string;
    role: 'user' | 'agent';
    text: string;
    attachments?: { url: string; type: string }[];
    timestamp: Date;
}

interface Client {
    id: number;
    name: string;
    external_id: string;
}

const ChatInterface: React.FC = () => {
    const [clients, setClients] = useState<Client[]>([]);
    const [selectedClient, setSelectedClient] = useState<string>('');
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputText, setInputText] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [attachments, setAttachments] = useState<{ url: string; type: string }[]>([]);
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<BlobPart[]>([]);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Fetch Clients on Mount
    useEffect(() => {
        const fetchClients = async () => {
            try {
                const data = await getClients();
                setClients(data);
                if (data.length > 0) setSelectedClient(data[0].external_id);
            } catch (err) {
                console.error("Failed to fetch clients", err);
            }
        };
        fetchClients();
    }, []);

    // Auto-scroll
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleSendMessage = async () => {
        if ((!inputText.trim() && attachments.length === 0) || !selectedClient) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            text: inputText,
            attachments: [...attachments],
            timestamp: new Date(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setInputText('');
        setAttachments([]);
        setIsLoading(true);

        try {
            // Build chat history from previous messages
            const chatHistory = messages
                .filter(m => !m.text.startsWith('⚠️ Error')) // Filter out local error messages
                .map(m => ({
                    role: m.role === 'user' ? 'user' : 'assistant',
                    content: m.text
                }));

            const payload = {
                message_id: `msg-${Date.now()}`,
                thread_id: `thread-${selectedClient}-user`, // Simple thread ID for demo
                client_external_id: selectedClient,
                text: userMsg.text,
                attachments: userMsg.attachments,
                chat_history: chatHistory,
            };

            const response = await sendMessage(payload);

            const agentMsg: Message = {
                id: Date.now().toString() + '_agent',
                role: 'agent',
                text: response.reply_text,
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, agentMsg]);
        } catch (error: any) {
            console.error("Error sending message:", error);
            const errorMessage = error.response?.data?.detail || error.message || "Failed to send message";
            setMessages((prev) => [...prev, {
                id: Date.now().toString() + '_error',
                role: 'agent',
                text: `⚠️ Error: ${errorMessage}`,
                timestamp: new Date(),
            } as Message]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setIsLoading(true);
            try {
                const result = await uploadFile(file);
                const type = file.type.startsWith('image/') ? 'image' : 'file';
                setAttachments((prev) => [...prev, { url: result.url, type }]);
            } catch (err) {
                console.error("Upload failed", err);
                alert("Upload failed");
            } finally {
                setIsLoading(false);
            }
        }
    };

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorderRef.current = new MediaRecorder(stream);
            chunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (e) => {
                if (e.data.size > 0) chunksRef.current.push(e.data);
            };

            mediaRecorderRef.current.onstop = async () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                // Note: OpenAI Whisper works best with mp3/wav/webm
                const file = new File([blob], "voice_message.webm", { type: 'audio/webm' });

                setIsLoading(true);
                try {
                    // Transcribe-First Architecture
                    // 1. Send audio to backend
                    const result = await transcribeAudio(file); // Returns { text: "..." }

                    // 2. Put text in input box for user review
                    if (result.text) {
                        setInputText(prev => prev ? `${prev} ${result.text}` : result.text);
                    }
                } catch (err) {
                    console.error("Voice transcription failed", err);
                    alert("Transcription failed");
                } finally {
                    setIsLoading(false);
                }
            };

            mediaRecorderRef.current.start();
            setIsRecording(true);
        } catch (err) {
            console.error("Could not access microphone", err);
            alert("Microphone access denied");
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
            // Stop all tracks
            mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
        }
    };

    return (
        <div className="flex flex-col h-[600px] w-full max-w-2xl mx-auto border rounded-xl shadow-lg bg-white overflow-hidden">
            {/* Header / Client Selector */}
            <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
                <h2 className="font-semibold text-lg">AI Assistant</h2>
                <select
                    className="p-2 border rounded-md text-sm"
                    value={selectedClient}
                    onChange={(e) => setSelectedClient(e.target.value)}
                >
                    {clients.map(c => (
                        <option key={c.id} value={c.external_id}>{c.name}</option>
                    ))}
                </select>
            </div>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50/50">
                {messages.map((msg) => (
                    <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] rounded-2xl p-3 ${msg.role === 'user'
                            ? 'bg-blue-600 text-white rounded-br-none'
                            : 'bg-white border text-gray-800 rounded-bl-none shadow-sm'
                            }`}>
                            {msg.attachments && msg.attachments.length > 0 && (
                                <div className="mb-2 space-y-2">
                                    {msg.attachments.map((att, idx) => (
                                        <div key={idx} className="rounded-lg overflow-hidden border">
                                            {att.type === 'image' ? (
                                                <img src={att.url} alt="attachment" className="max-w-full h-auto max-h-48 object-cover" />
                                            ) : (
                                                <div className="p-2 text-xs bg-gray-100 flex items-center gap-1">
                                                    <Paperclip className="w-3 h-3" /> File
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                            <div className="whitespace-pre-wrap">{msg.text}</div>
                        </div>
                    </div>
                ))}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white border p-3 rounded-2xl rounded-bl-none shadow-sm">
                            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div className="p-4 bg-white border-t">
                {/* Attachments Preview */}
                {attachments.length > 0 && (
                    <div className="flex gap-2 mb-2 overflow-x-auto p-1">
                        {attachments.map((att, idx) => (
                            <div key={idx} className="relative group">
                                <div className="w-16 h-16 rounded-md border overflow-hidden bg-gray-100 flex items-center justify-center">
                                    {att.type === 'image' ? (
                                        <img src={att.url} className="w-full h-full object-cover" />
                                    ) : (
                                        <Paperclip className="w-6 h-6 text-gray-400" />
                                    )}
                                </div>
                                <button
                                    onClick={() => setAttachments(prev => prev.filter((_, i) => i !== idx))}
                                    className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                                >
                                    <X className="w-3 h-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                <div className="flex items-end gap-2">
                    <button
                        onClick={() => fileInputRef.current?.click()}
                        className="p-2 text-gray-500 hover:bg-gray-100 rounded-full transition-colors"
                        title="Upload File"
                    >
                        <ImageIcon className="w-5 h-5" />
                    </button>
                    <input
                        type="file"
                        ref={fileInputRef}
                        className="hidden"
                        onChange={handleFileSelect}
                        accept="image/*,.pdf,.txt" // Allow images and basic docs
                    />

                    <button
                        onMouseDown={startRecording}
                        onMouseUp={stopRecording}
                        onMouseLeave={stopRecording}
                        className={`p-2 rounded-full transition-colors ${isRecording ? 'bg-red-100 text-red-600 animate-pulse' : 'text-gray-500 hover:bg-gray-100'
                            }`}
                        title="Hold to Record"
                    >
                        <Mic className="w-5 h-5" />
                    </button>

                    <div className="flex-1 relative">
                        <textarea
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSendMessage();
                                }
                            }}
                            placeholder={isRecording ? "Recording..." : "Type a message..."}
                            className="w-full resize-none border rounded-xl p-3 pr-10 max-h-32 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                            rows={1}
                        />
                    </div>

                    <button
                        onClick={handleSendMessage}
                        disabled={(!inputText.trim() && attachments.length === 0) || isLoading}
                        className="p-3 bg-blue-600 text-white rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        <Send className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ChatInterface;
