'use client';

import { useState } from 'react';
import Link from 'next/link';
import ThemeToggle from './ThemeToggle';
import HealthIndicator from './HealthIndicator';

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);

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
          <div className="flex items-center space-x-2">
            <HealthIndicator />
            <ThemeToggle />
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="sm:hidden p-2 rounded-full hover:bg-gray-700 transition-colors"
              aria-label="Toggle menu"
            >
              {menuOpen ? (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
      {menuOpen && (
        <div className="sm:hidden border-t border-gray-700">
          <div className="px-4 py-3 space-y-1">
            <Link href="/" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
              Home
            </Link>
            <Link href="/images" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
              Images
            </Link>
            <a href="/health" target="_blank" rel="noopener noreferrer" className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
              Health
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
