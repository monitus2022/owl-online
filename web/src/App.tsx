import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { SiteFooter } from "./components/SiteFooter";
import { useStudentName } from "./data/student";
import { AboutPage } from "./pages/AboutPage";
import { CloisterPage } from "./pages/CloisterPage";
import { FrontPage } from "./pages/FrontPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { VenuePage } from "./pages/VenuePage";
import { WelcomePage } from "./pages/WelcomePage";

// The only pages that may be read before the student is named. The welcome
// links both, so the privacy notice is reachable from the first screen.
const PUBLIC_PATHS = new Set(["/about", "/privacy"]);

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
  const studentName = useStudentName();
  // A hard gate: no name, no route beyond the two public pages. The name is
  // the student's own, kept in localStorage; the API never stores it.
  const admitted =
    studentName !== null || PUBLIC_PATHS.has(location.pathname);
  return (
    <div
      className="route-fade"
      key={`${location.pathname}:${admitted}`}
    >
      {admitted ? (
        <Routes location={location}>
          <Route path="/" element={<FrontPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/cloister" element={<CloisterPage />} />
          <Route path="/venue/:slug" element={<VenuePage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      ) : (
        <WelcomePage />
      )}
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
