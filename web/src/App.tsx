import { BrowserRouter, Route, Routes } from "react-router-dom";
import { SiteFooter } from "./components/SiteFooter";
import { CloisterPage } from "./pages/CloisterPage";
import { FrontPage } from "./pages/FrontPage";
import { VenuePage } from "./pages/VenuePage";

export default function App() {
  return (
    <BrowserRouter>
      {/* The footer sits beside the pages, not inside their main element, so
          it maps to the contentinfo landmark. New routes inherit it. */}
      <Routes>
        <Route path="/" element={<FrontPage />} />
        <Route path="/cloister" element={<CloisterPage />} />
        <Route path="/venue/:slug" element={<VenuePage />} />
      </Routes>
      <SiteFooter />
    </BrowserRouter>
  );
}
