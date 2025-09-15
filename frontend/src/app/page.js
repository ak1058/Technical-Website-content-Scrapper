"use client"
import React, { useState, useEffect, useRef } from 'react';
import { Play, Download, Globe, Clock, CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react';

const WebScraperApp = () => {
  const [url, setUrl] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [logs, setLogs] = useState([]);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [result, setResult] = useState(null);
  const [maxItems, setMaxItems] = useState(20);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const eventSourceRef = useRef(null);
  const logsEndRef = useRef(null);

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [logs]);

  const getLogIcon = (type, isProcessingCompleted = false) => {
    switch (type) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />;
      case 'error':
        return <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />;
      case 'warning':
        return <AlertCircle className="w-4 h-4 text-yellow-500 flex-shrink-0" />;
      case 'progress':
        // Stop spinning if scraping is completed
        return <Loader2 className={`w-4 h-4 text-blue-500 flex-shrink-0 ${!isProcessingCompleted ? 'animate-spin' : ''}`} />;
      default:
        return <Globe className="w-4 h-4 text-gray-500 flex-shrink-0" />;
    }
  };

  const getLogColor = (type) => {
    switch (type) {
      case 'success':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'error':
        return 'text-red-700 bg-red-50 border-red-200';
      case 'warning':
        return 'text-yellow-700 bg-yellow-50 border-yellow-200';
      case 'progress':
        return 'text-blue-700 bg-blue-50 border-blue-200';
      case 'complete':
        return 'text-emerald-700 bg-emerald-50 border-emerald-200';
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200';
    }
  };

  const startScraping = async () => {
    if (!url.trim()) {
      alert('Please enter a URL to scrape');
      return;
    }

    setIsStreaming(true);
    setLogs([]);
    setProgress({ current: 0, total: 0 });
    setResult(null);
    setIsCompleted(false);

    try {
      eventSourceRef.current = new EventSource('http://localhost:8000/scrape/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      // Send the request data (Note: EventSource doesn't support POST body directly)
      // So we'll use fetch with a streaming response
      const response = await fetch('http://localhost:8000/scrape/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: url,
          max_items: maxItems,
          respect_robots: false
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'progress') {
                setProgress({ current: data.current, total: data.total });
                setLogs(prev => [...prev, {
                  id: Date.now() + Math.random(),
                  type: data.type,
                  message: `Processing URL ${data.current}/${data.total}: ${data.url}`,
                  timestamp: new Date().toLocaleTimeString()
                }]);
              } else if (data.type === 'complete') {
                setResult(data.result);
                setIsCompleted(true);
                setLogs(prev => [...prev, {
                  id: Date.now() + Math.random(),
                  type: data.type,
                  message: data.message,
                  timestamp: new Date().toLocaleTimeString()
                }]);
              } else {
                setLogs(prev => [...prev, {
                  id: Date.now() + Math.random(),
                  type: data.type,
                  message: data.message,
                  timestamp: new Date().toLocaleTimeString()
                }]);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      setLogs(prev => [...prev, {
        id: Date.now(),
        type: 'error',
        message: `Connection error: ${error.message}`,
        timestamp: new Date().toLocaleTimeString()
      }]);
    } finally {
      setIsStreaming(false);
      setIsCompleted(true);
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    }
  };

  const stopScraping = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setIsStreaming(false);
    setIsCompleted(true);
  };

  const downloadResults = async () => {
    if (!result) return;
    
    setIsDownloading(true);
    
    // Simulate some processing time for the download
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    try {
      const dataStr = JSON.stringify(result, null, 2);
      const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
      
      const exportFileDefaultName = `scraped_data_${new Date().toISOString().split('T')[0]}.json`;
      
      const linkElement = document.createElement('a');
      linkElement.setAttribute('href', dataUri);
      linkElement.setAttribute('download', exportFileDefaultName);
      linkElement.click();
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <div className="bg-black/20 backdrop-blur-sm border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg">
              <Globe className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Universal Web Scraper</h1>
              <p className="text-gray-300 text-sm">Extract content from any website with real-time progress</p>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Input Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl border border-white/20 p-6 shadow-2xl">
              <h2 className="text-lg font-semibold text-white mb-6 flex items-center">
                <Play className="w-5 h-5 mr-2" />
                Configuration
              </h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Website URL
                  </label>
                  <input
                    type="url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.com"
                    className="w-full px-4 py-3 bg-black/30 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    disabled={isStreaming}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">
                      Max Items
                    </label>
                    <input
                      type="number"
                      value={maxItems}
                      onChange={(e) => setMaxItems(parseInt(e.target.value) || 10)}
                      min="1"
                      max="50"
                      className="w-full px-3 py-2 bg-black/30 border border-white/20 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={isStreaming}
                    />
                  </div>
                  
                </div>

                <button
                  onClick={isStreaming ? stopScraping : startScraping}
                  disabled={!url.trim() && !isStreaming}
                  className={`w-full py-3 px-4 rounded-lg font-medium transition-all duration-200 ${
                    isStreaming
                      ? 'bg-red-600 hover:bg-red-700 text-white'
                      : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white disabled:opacity-50 disabled:cursor-not-allowed'
                  }`}
                >
                  {isStreaming ? (
                    <>
                      <XCircle className="w-5 h-5 inline mr-2" />
                      Stop Scraping
                    </>
                  ) : (
                    <>
                      <Play className="w-5 h-5 inline mr-2" />
                      Start Scraping
                    </>
                  )}
                </button>

                {result && (
                  <button
                    onClick={downloadResults}
                    disabled={isDownloading}
                    className="w-full py-3 px-4 bg-green-600 hover:bg-green-700 disabled:bg-green-400 text-white rounded-lg font-medium transition-all duration-200 cursor-pointer"
                  >
                    {isDownloading ? (
                      <>
                        <Loader2 className="w-5 h-5 inline mr-2 animate-spin cursor-pointer" />
                        Downloading...
                      </>
                    ) : (
                      <>
                        <Download className="w-5 h-5 inline mr-2 cursor-pointer" />
                        Download Output Json
                      </>
                    )}
                  </button>
                )}
              </div>

              {/* Progress Bar */}
              {progress.total > 0 && (
                <div className="mt-6">
                  <div className="flex justify-between text-sm text-gray-300 mb-2">
                    <span>Progress</span>
                    <span>{progress.current}/{progress.total}</span>
                  </div>
                  <div className="w-full bg-black/30 rounded-full h-2">
                    <div 
                      className="bg-gradient-to-r from-blue-500 to-purple-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(progress.current / progress.total) * 100}%` }}
                    ></div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Logs Panel */}
          <div className="lg:col-span-2">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl border border-white/20 shadow-2xl">
              <div className="p-6 border-b border-white/20">
                <h2 className="text-lg font-semibold text-white flex items-center">
                  <Clock className="w-5 h-5 mr-2" />
                  Real-time Logs
                  {logs.length > 0 && (
                    <span className="ml-2 px-2 py-1 bg-blue-600 text-white text-xs rounded-full">
                      {logs.length}
                    </span>
                  )}
                </h2>
              </div>
              
              <div className="h-96 overflow-y-auto p-4 space-y-3">
                {logs.length === 0 ? (
                  <div className="text-center text-gray-400 py-8">
                    <Globe className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>No logs yet. Start scraping to see real-time progress.</p>
                  </div>
                ) : (
                  logs.map((log) => (
                    <div
                      key={log.id}
                      className={`flex items-start space-x-3 p-3 rounded-lg border transition-all duration-200 ${getLogColor(log.type)}`}
                    >
                      {getLogIcon(log.type, isCompleted)}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium break-words">{log.message}</p>
                        <p className="text-xs opacity-70 mt-1">{log.timestamp}</p>
                      </div>
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        </div>

        {/* Results Panel */}
        {result && (
          <div className="mt-8">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl border border-white/20 shadow-2xl">
              <div className="p-6 border-b border-white/20">
                <h2 className="text-lg font-semibold text-white flex items-center justify-between">
                  <span className="flex items-center">
                    <CheckCircle className="w-5 h-5 mr-2 text-green-500" />
                    Scraping Results
                  </span>
                  <div className="text-sm text-gray-300">
                    {result.summary.total_items} items found
                  </div>
                </h2>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                  <div className="bg-black/30 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-green-400">{result.summary.total_items}</div>
                    <div className="text-sm text-gray-300">Items Extracted</div>
                  </div>
                  <div className="bg-black/30 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-red-400">{result.summary.total_errors}</div>
                    <div className="text-sm text-gray-300">Errors</div>
                  </div>
                  <div className="bg-black/30 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-blue-400">{result.site}</div>
                    <div className="text-sm text-gray-300 truncate">Source Site</div>
                  </div>
                </div>

                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {result.items.map((item, index) => (
                    <div key={index} className="bg-black/30 rounded-lg p-4 border border-white/10">
                      <div className="flex justify-between items-start mb-2">
                        <h3 className="font-semibold text-white text-lg">{item.title}</h3>
                        <span className="px-2 py-1 bg-blue-600 text-white text-xs rounded-full">
                          {item.content_type}
                        </span>
                      </div>
                      <p className="text-gray-300 text-sm mb-2 line-clamp-3">
                        {item.content.replace(/[#*`]/g, '').substring(0, 200)}...
                      </p>
                      <div className="flex justify-between items-center text-xs text-gray-400">
                        <span>Length: {item.content.length} chars</span>
                        <a 
                          href={item.source_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="text-blue-400 hover:text-blue-300 underline"
                        >
                          View Source
                        </a>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default WebScraperApp;