'use client'

import { FileText, MessageSquare, Image, Headphones, ExternalLink } from 'lucide-react'
import { format } from 'date-fns'
import { ja } from 'date-fns/locale'

interface Source {
  id: string
  title: string
  content: string
  document_type: string
  platform?: string
  similarity_score: number
  created_at: string
  metadata?: any
}

interface SourceCardProps {
  source: Source
}

export default function SourceCard({ source }: SourceCardProps) {
  const getIcon = () => {
    switch (source.document_type) {
      case 'chat':
        return <MessageSquare className="h-4 w-4" />
      case 'pdf':
        return <FileText className="h-4 w-4" />
      case 'image':
        return <Image className="h-4 w-4" />
      case 'audio':
        return <Headphones className="h-4 w-4" />
      default:
        return <FileText className="h-4 w-4" />
    }
  }

  const getPlatformBadge = () => {
    if (!source.platform) return null
    
    const platformColors = {
      slack: 'bg-purple-100 text-purple-800',
      line: 'bg-green-100 text-green-800',
      chatwork: 'bg-blue-100 text-blue-800'
    }
    
    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
        platformColors[source.platform as keyof typeof platformColors] || 'bg-gray-100 text-gray-800'
      }`}>
        {source.platform.toUpperCase()}
      </span>
    )
  }

  const getSimilarityColor = () => {
    const score = source.similarity_score
    if (score >= 0.9) return 'text-green-600'
    if (score >= 0.8) return 'text-yellow-600'
    return 'text-gray-600'
  }

  return (
    <div className="source-card card p-4 hover:shadow-md transition-all duration-200">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center space-x-2 flex-1 min-w-0">
          <div className="text-gray-500">
            {getIcon()}
          </div>
          <h4 className="font-medium text-gray-900 truncate">
            {source.title}
          </h4>
        </div>
        <div className="flex items-center space-x-2 flex-shrink-0 ml-2">
          {getPlatformBadge()}
          <button className="text-gray-400 hover:text-primary-600 transition-colors">
            <ExternalLink className="h-3 w-3" />
          </button>
        </div>
      </div>
      
      <p className="text-gray-700 text-sm mb-3 line-clamp-3">
        {source.content.length > 150 
          ? `${source.content.substring(0, 150)}...` 
          : source.content
        }
      </p>
      
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>
          {format(new Date(source.created_at), 'yyyy/MM/dd HH:mm', { locale: ja })}
        </span>
        <span className={`font-medium ${getSimilarityColor()}`}>
          関連度: {Math.round(source.similarity_score * 100)}%
        </span>
      </div>
      
      {/* Additional metadata */}
      {source.metadata && (
        <div className="mt-2 pt-2 border-t border-gray-100">
          {source.metadata.user_name && (
            <div className="text-xs text-gray-500">
              投稿者: {source.metadata.user_name}
            </div>
          )}
          {source.metadata.channel_name && (
            <div className="text-xs text-gray-500">
              チャンネル: {source.metadata.channel_name}
            </div>
          )}
        </div>
      )}
    </div>
  )
}