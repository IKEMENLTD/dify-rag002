'use client'

import { Menu, Search, Upload, Settings } from 'lucide-react'

interface HeaderProps {
  onMenuClick: () => void
  sidebarOpen: boolean
}

export default function Header({ onMenuClick, sidebarOpen }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3">
      <div className="flex items-center justify-between">
        {/* Left section */}
        <div className="flex items-center space-x-4">
          <button
            onClick={onMenuClick}
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
          >
            <Menu className="h-5 w-5" />
          </button>
          
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">V</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">ベテランAI</h1>
              <p className="text-sm text-gray-500">Enterprise Knowledge AI</p>
            </div>
          </div>
        </div>
        
        {/* Right section */}
        <div className="flex items-center space-x-2">
          <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-600">
            <Search className="h-5 w-5" />
          </button>
          <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-600">
            <Upload className="h-5 w-5" />
          </button>
          <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-600">
            <Settings className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  )
}