import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import Library from "./pages/Library";
import ModelDetail from "./pages/ModelDetail";
import Creators from "./pages/Creators";
import Collections from "./pages/Collections";
import BackToTop from "./components/BackToTop";

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/models/:id" element={<ModelDetail />} />
          <Route path="/creators" element={<Creators />} />
          <Route path="/collections" element={<Collections />} />
        </Routes>
      </main>
      <BackToTop />
    </div>
  );
}
