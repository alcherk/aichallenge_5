import React from 'react';

interface AppLayoutProps {
  children: React.ReactNode;
  header?: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({ children, header }) => {
  return (
    <div className="flex flex-col h-screen bg-slate-950">
      {/* Header */}
      {header && (
        <header className="bg-slate-900 border-b border-slate-700 px-6 py-4 shadow-lg">
          {header}
        </header>
      )}

      {/* Main content */}
      <main className="flex-1 overflow-hidden">{children}</main>

      {/* Footer */}
      <footer className="bg-slate-900 border-t border-slate-700 px-6 py-2 text-center text-sm text-slate-400">
        Backend: FastAPI · Port 8333 · Docker-ready
      </footer>
    </div>
  );
};
