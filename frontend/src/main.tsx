import React from "react";
import ReactDOM from "react-dom/client";
import { ActivityDashboard } from "./ActivityDashboard";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ActivityDashboard />
  </React.StrictMode>,
);
