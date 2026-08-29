import React, { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex w-full min-h-screen bg-surface">

      {/* Fixed sidebar */}
      <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />

      {/* Content area: takes all remaining width */}
      <div className="flex flex-col flex-1 min-h-screen overflow-hidden lg:ml-[210px]">
        <Header onMenuClick={() => setSidebarOpen(true)} />
        <main className="flex-1 p-5 lg:p-7 w-full overflow-y-scroll overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
