import { Link } from "react-router-dom";
import { AcademyFront } from "../components/AcademyFront";

// The front gate once the student is named. Same building as the first-run
// gate at full scale; the next step is the cloister of department doors.
export function FrontPage() {
  return (
    <AcademyFront full>
      <Link to="/cloister" className="btn-primary enter-btn">
        Enter the cloister
      </Link>
    </AcademyFront>
  );
}
