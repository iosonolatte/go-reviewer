import React from "react";
import { Link, useLocation } from "react-router-dom";
import { CircleDot, Settings, Home } from "lucide-react";
import { cn } from "../lib/utils";

const Navbar: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: "/", icon: Home, label: "首页" },
    { path: "/review", icon: CircleDot, label: "复盘" },
    { path: "/settings", icon: Settings, label: "设置" },
  ];

  return (
    <nav className="bg-gradient-to-r from-go-wood to-go-woodLight text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-go-board flex items-center justify-center">
              <CircleDot className="w-6 h-6 text-go-wood" />
            </div>
            <span className="text-xl font-serif font-bold">围棋复盘 AI</span>
          </Link>

          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const isActive = location.pathname === item.path;
              const Icon = item.icon;

              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg transition-all",
                    isActive
                      ? "bg-white/20 text-white"
                      : "text-white/70 hover:bg-white/10 hover:text-white",
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="font-medium">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
