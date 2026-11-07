import { BrowserRouter, Route, Routes } from "react-router-dom";
import { CloisterPage } from "./pages/CloisterPage";
import { FrontPage } from "./pages/FrontPage";
import { VenuePage } from "./pages/VenuePage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<FrontPage />} />
        <Route path="/cloister" element={<CloisterPage />} />
        <Route path="/venue/:slug" element={<VenuePage />} />
      </Routes>
    </BrowserRouter>
  );
}
