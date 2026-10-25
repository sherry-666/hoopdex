import { Link } from "react-router-dom";
import { useLang, usePageTitle } from "../i18n";

export default function ComingSoon({ title, line }: { title: string; line: string }) {
  const { t } = useLang();
  usePageTitle(title);
  return (
    <section className="panel halftone" style={{ textAlign: "center", padding: "48px 24px" }}>
      <div className="burst" style={{ margin: "0 auto 18px", minWidth: 180, minHeight: 150 }}>
        <span className="num" style={{ fontSize: 34 }}>SOON!</span>
      </div>
      <h1 style={{ fontSize: "var(--size-h1)" }}>{title}</h1>
      <p style={{ maxWidth: "48ch", margin: "10px auto 18px" }}>{line}</p>
      <Link to="/roles" className="btn primary">{t("先去定位实验室")}</Link>
    </section>
  );
}
