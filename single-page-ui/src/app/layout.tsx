import type { Metadata } from "next";
import "./globals.css";
import DisclaimerBanner from "./disclaimer-banner";
import AppInitializer from "@/components/AppInitializer";

export const metadata: Metadata = {
  title: "License Plate Recognition",
  description: "Upload images to detect and recognize license plates using AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('lpr-theme');
                  if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                    document.documentElement.classList.add('dark');
                  }
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-screen bg-white text-gray-900 dark:bg-[#0f0f0f] dark:text-gray-100 transition-colors duration-300">
        <nav className="bg-gray-800 dark:bg-[#0f0f0f] text-white shadow-lg sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center space-x-8">
                <a href="/" className="text-xl font-semibold tracking-tight">
                  Open LPR
                </a>
                <div className="hidden sm:flex items-center space-x-4">
                  <a href="/" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                    Home
                  </a>
                  <a href="/images" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                    Images
                  </a>
                  <a href="/health" target="_blank" rel="noopener noreferrer" className="px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                    Health
                  </a>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  id="theme-toggle"
                  className="p-2 rounded-full hover:bg-gray-700 transition-colors"
                  aria-label="Toggle theme"
                >
                  <svg className="w-5 h-5 hidden dark:block" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                  <svg className="w-5 h-5 block dark:hidden" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                </button>
                <button
                  id="mobile-menu-toggle"
                  className="sm:hidden p-2 rounded-full hover:bg-gray-700 transition-colors"
                  aria-label="Toggle menu"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <div id="mobile-menu" className="hidden sm:hidden border-t border-gray-700">
            <div className="px-4 py-3 space-y-1">
              <a href="/" className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                Home
              </a>
              <a href="/images" className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                Images
              </a>
              <a href="/health" target="_blank" rel="noopener noreferrer" className="block px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition-colors">
                Health
              </a>
            </div>
          </div>
        </nav>

        <DisclaimerBanner />

        <main className="flex-1">
          <AppInitializer>
            {children}
          </AppInitializer>
        </main>

        <footer className="bg-gray-100 dark:bg-[#1a1a1a] border-t border-gray-200 dark:border-gray-700 mt-12">
          <div className="max-w-7xl mx-auto px-4 py-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-sm text-gray-500 dark:text-gray-400">
            <span>Open LPR &mdash; License Plate Recognition</span>
            <div className="flex items-center gap-4">
              <span>
                Powered by{' '}
                <a
                  href="https://github.com/QwenLM/Qwen3-VL"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-purple-600 dark:text-purple-400 hover:underline"
                >
                  Qwen3-VL
                </a>
              </span>
              <a
                href="https://github.com/faisalthaheem/open-lpr"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
                </svg>
                GitHub
              </a>
            </div>
          </div>
        </footer>

        <script
          dangerouslySetInnerHTML={{
            __html: `
              document.getElementById('theme-toggle').addEventListener('click', function() {
                var html = document.documentElement;
                if (html.classList.contains('dark')) {
                  html.classList.remove('dark');
                  localStorage.setItem('lpr-theme', 'light');
                } else {
                  html.classList.add('dark');
                  localStorage.setItem('lpr-theme', 'dark');
                }
              });
              document.getElementById('mobile-menu-toggle').addEventListener('click', function() {
                var menu = document.getElementById('mobile-menu');
                menu.classList.toggle('hidden');
              });
            `,
          }}
        />
      </body>
    </html>
  );
}
