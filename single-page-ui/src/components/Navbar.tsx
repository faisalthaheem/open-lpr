'use client';

import Link from 'next/link';
import ThemeToggle from './ThemeToggle';

export default function Navbar() {
  return (
    <nav className="bg-gray-800 dark:bg-[#0f0f0f] text-white shadow-lg sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link href="/" className="text-xl font-semibold tracking-tight">
              Open LPR
            </Link>
            <div className="hidden sm:flex items-center space-x-4">
              <Link href="/" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                Home
              </Link>
              <Link href="/images" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                Images
              </Link>
              <a href="/health" target="_blank" rel="noopener noreferrer" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                Health
              </a>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <ThemeToggle />
          </div>
        </div>
      </div>
    </nav>
  );
}
