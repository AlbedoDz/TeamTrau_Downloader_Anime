import React, { useState, useEffect } from 'react';
import { Shell } from './components/Shell';
import { ManagerToolbar } from './components/ManagerToolbar';
import { SidebarCategories } from './components/SidebarCategories';
import { DownloadTableView } from './components/DownloadTableView';
import { TaskDetailModal } from './components/TaskDetailModal';
import { UrlInputHero } from './components/UrlInputHero';
import { BatchOptionsModal } from './components/BatchOptionsModal';
import { ConsoleDrawer } from './components/ConsoleDrawer';
import { SettingsDrawer } from './components/SettingsDrawer';
import { downloadStore, ManagerState } from './state/useDownloadStore';

export const App: React.FC = () => {
  const [state, setState] = useState<ManagerState>(downloadStore.getState());
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = downloadStore.subscribe(() => {
      setState(downloadStore.getState());
    });

    return () => {
      unsubscribe();
    };
  }, []);

  const selectedTask = state.tasks.find((t) => t.id === state.selectedTaskId) || null;

  return (
    <Shell>
      <div className="flex-1 flex flex-col h-[calc(100vh-64px)] overflow-hidden bg-[#0B0F17]">
        {/* Top Manager Toolbar */}
        <ManagerToolbar
          onOpenAddModal={() => setIsAddModalOpen(true)}
          onOpenSettings={() => setIsSettingsOpen(true)}
        />

        {/* Main Grid: Sidebar Categories + IDM Table View */}
        <div className="flex-1 flex overflow-hidden">
          <SidebarCategories
            counts={state.counts}
            selectedCategory={state.selectedCategory}
          />
          <DownloadTableView tasks={state.tasks} />
        </div>

        {/* Add URL / Download Input Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#05080E]/80 backdrop-blur-md">
            <div className="relative w-full max-w-2xl bg-[#161F30] border border-white/10 rounded-2xl shadow-2xl overflow-hidden p-6 animate-in fade-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between pb-4 border-b border-white/10">
                <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
                  <span>⚡</span> Thêm Tác Vụ Tải Anime Mới
                </h2>
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="text-slate-400 hover:text-white p-1 rounded-lg"
                >
                  ✕
                </button>
              </div>
              <div className="py-4">
                <UrlInputHero />
              </div>
            </div>
          </div>
        )}

        {/* Batch Options Modal */}
        <BatchOptionsModal />

        {/* Per-Task Detail & Logs Modal */}
        {state.isTaskDetailOpen && (
          <TaskDetailModal
            task={selectedTask}
            logs={state.taskLogs}
            onClose={() => downloadStore.closeTaskDetail()}
          />
        )}

        {/* Settings Drawer */}
        <SettingsDrawer
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
        />

        {/* Console Drawer */}
        <ConsoleDrawer />
      </div>
    </Shell>
  );
};
