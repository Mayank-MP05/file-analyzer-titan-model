// pages/index.js
"use client"
import { useState, useRef, useEffect } from 'react';
import Head from 'next/head';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';
import MarkdownRenderer from './MarkdownRenderer';

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [fileUploaded, setFileUploaded] = useState(false);
  const [fileName, setFileName] = useState('');
  const [streamingMessage, setStreamingMessage] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingMessage]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Add validation for file types
    if (!file.name.endsWith('.xlsx')) {
      alert('Please upload an Excel file (.xlsx)');
      return;
    }

    setLoading(true);
    setFileName(file.name);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:5000/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setMessages([
        ...messages,
        { role: 'system', content: `File ${file.name} uploaded successfully. You can now ask questions about the data.` }
      ]);
      setFileUploaded(true);
    } catch (error) {
      let errorToPrint = error?.error || error; 
      console.error('Error uploading file:', errorToPrint);
      setMessages([
        ...messages,
        { role: 'system', content: `Error uploading file: ${errorToPrint}` }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = { role: 'user', content: input };
    setMessages([...messages, userMessage]);
    setInput('');
    setLoading(true);
    setStreamingMessage(''); // Reset streaming message

    try {
      // Add the empty assistant message that will be filled by streaming
      setMessages(prevMessages => [...prevMessages, { role: 'assistant', content: '' }]);
      
      // Start streaming
      await fetchStreamingResponse(input);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prevMessages => [
        ...prevMessages.slice(0, -1), // Remove the empty assistant message
        { role: 'system', content: `Error: ${error.message}` }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fetchStreamingResponse = async (message) => {
    try {
      // Make a fetch request instead of using axios for better streaming support
      const response = await fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message, stream: true }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Set up the reader for the stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedResponse = '';

      // Process the stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Decode the chunk
        const chunk = decoder.decode(value, { stream: true });
        
        // Process SSE format: each data message starts with 'data: ' and ends with '\n\n'
        const lines = chunk.split('\n\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              
              if (data.text) {
                accumulatedResponse += data.text;
                
                // Update the last message in the messages array (the assistant's response)
                setMessages(prevMessages => {
                  const newMessages = [...prevMessages];
                  newMessages[newMessages.length - 1] = {
                    ...newMessages[newMessages.length - 1],
                    content: accumulatedResponse
                  };
                  return newMessages;
                });
              }
              
              if (data.error) {
                throw new Error(data.error);
              }
            } catch (e) {
              if (e.message !== "Unexpected end of JSON input") {
                console.error('Error parsing streaming data:', e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Streaming error:', error);
      throw error;
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      <Head>
        <title>Fibe GPT</title>
        <meta name="description" content="Chat with your Excel files" />
      </Head>

      <header className="bg-[#079f9f] text-white p-4">
        <h1 className="text-2xl font-bold">Fibe GPT</h1>
      </header>

      <main className="flex-1 flex flex-col max-w-4xl mx-auto w-full p-4">
        <div className="mb-4">
          <div className="flex items-center space-x-2">
            <label className="bg-[#079f9f] hover:bg-[#079f9f] text-white py-2 px-4 rounded cursor-pointer">
              {fileUploaded ? 'Change File' : 'Upload Excel File'}
              <input
                type="file"
                className="hidden"
                onChange={handleFileUpload}
                accept=".xlsx"
              />
            </label>
            {fileName && (
              <span className="text-sm text-gray-600">
                {fileName}
              </span>
            )}
            {loading && (
              <div className="ml-2">
                <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-[#079f9f]"></div>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 bg-white rounded-lg shadow overflow-hidden flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 mt-10">
                <p>Upload an Excel file to start chatting</p>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={index}
                  className={`${
                    msg.role === 'user'
                      ? 'bg-[#c5eeee] ml-auto'
                      : msg.role === 'system'
                      ? 'bg-gray-100'
                      : 'bg-[#eafafa]'
                  } rounded-lg p-3 max-w-[80%] text-black ${
                    msg.role === 'user' ? 'ml-auto' : ''
                  }`}
                >
                  <MarkdownRenderer content={msg.content}></MarkdownRenderer>
                </div>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSendMessage} className="border-t p-4">
            <div className="flex space-x-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={!fileUploaded || loading}
                placeholder={
                  !fileUploaded
                    ? "Upload a file first"
                    : loading
                    ? "Processing..."
                    : "Type your message here..."
                }
                className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-[#079f9f] text-black"
              />
              <button
                type="submit"
                disabled={!fileUploaded || loading || !input.trim()}
                className={`bg-[#079f9f] text-white px-4 py-2 rounded-lg ${
                  !fileUploaded || loading || !input.trim()
                    ? 'opacity-50 cursor-not-allowed'
                    : 'hover:bg-[#079f9f]'
                }`}
              >
                Send
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}