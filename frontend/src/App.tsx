import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import Landing from "@/pages/Landing";
import Documents from "@/pages/Documents";
import Analyze from "@/pages/Analyze";
import Compare from "@/pages/Compare";
import ActionPack from "@/pages/ActionPack";
import Settings from "@/pages/Settings";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/analyze" element={<Analyze />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/action-pack" element={<ActionPack />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}