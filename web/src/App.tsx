import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { SiteFooter } from "./components/SiteFooter";
import { AboutPage } from "./pages/AboutPage";
import { CloisterPage } from "./pages/CloisterPage";
import { FrontPage } from "./pages/FrontPage";
import { VenuePage } from "./pages/VenuePage";

// One entering animation per route change: the wrapper is keyed on the path,
// so any navigation remounts it and the CSS plays once. In-page state (the
// venue tabs) never touches the URL, so tab switches do not re-trigger it,
// and prefers-reduced-motion cancels the animation outright.
//
// The key carries a second, load-bearing invariant: venue-to-venue
// navigation remounts the page, so one department's transcript and in-flight
// paper cannot render under another's identity. If this animation is ever
// removed, keep remount-on-pathname explicit (for example a key on the
// venue element itself).
function Shell() {
  const location = useLocation();
  return (
    <div className="route-fade" key={location.pathname}>
      <Routes location={location}>
        <Route path="/" element={<FrontPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/cloister" element={<CloisterPage />} />
        <Route path="/venue/:slug" element={<VenuePage />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
      {/* The footer sits beside the pages, not inside their main element, so
          it maps to the contentinfo landmark. New routes inherit it. */}
      <SiteFooter />
    </BrowserRouter>
  );
}
