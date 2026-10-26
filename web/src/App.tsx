import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { useLang } from "./i18n";
import Home from "./pages/Home";
import RolesLab from "./pages/RolesLab";
import Roster from "./pages/Roster";
import Teams from "./pages/Teams";
import PlayerPage from "./pages/PlayerPage";
import ComingSoon from "./pages/ComingSoon";

type Theme = "light" | "dark" | null;

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem("theme") as Theme) ?? null; } catch { return null; }
  });
  useEffect(() => {
    if (theme) document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
    try { theme ? localStorage.setItem("theme", theme) : localStorage.removeItem("theme"); } catch { /* storage blocked */ }
  }, [theme]);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setSystemDark(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const dark = theme ? theme === "dark" : systemDark;
  return [dark ? "dark" : "light", () => setTheme(dark ? "light" : "dark")];
}

export default function App() {
  const [theme, toggle] = useTheme();
  const { t, lang, setLang } = useLang();
  return (
    <>
      <header className="masthead">
        <NavLink to="/" className="logo">HOOPDEX!</NavLink>
        <nav className="nav" aria-label={t("主导航")}>
          <NavLink to="/" end>{t("首页")}</NavLink>
          <NavLink to="/roles">{t("定位实验室")}</NavLink>
          <NavLink to="/players">{t("球员名册")}</NavLink>
          <NavLink to="/teams">{t("球队体系")}</NavLink>
          <NavLink to="/predict">{t("比赛预测")}</NavLink>
          <NavLink to="/trade">{t("交易模拟")}</NavLink>
        </nav>
        <div className="row masthead-tools">
          <div className="lang-switch" role="group" aria-label="语言 / Language">
            <button type="button" aria-pressed={lang === "zh"} onClick={() => setLang("zh")}>中文</button>
            <button type="button" aria-pressed={lang === "en"} onClick={() => setLang("en")}>EN</button>
          </div>
          <button type="button" className="theme-toggle" onClick={toggle}>{theme === "dark" ? t("日间版") : t("夜间版")}</button>
        </div>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/roles" element={<RolesLab />} />
          <Route path="/players" element={<Roster />} />
          <Route path="/players/:id" element={<PlayerPage />} />
          <Route path="/teams" element={<Teams />} />
          <Route path="/predict" element={<ComingSoon title={t("比赛预测")} line={t("选两支球队，看胜率和分差。球员影响力模型完成后上线。")} />} />
          <Route path="/trade" element={<ComingSoon title={t("交易模拟")} line={t("把球员拖到另一队，看强度和适配度怎么变。比赛预测上线后接着做。")} />} />
          <Route path="*" element={<ComingSoon title={t("走错片场了")} line={t("这一页不存在。回首页看看其他球员吧。")} />} />
        </Routes>
      </main>
      <footer className="site-footer">{t("HoopDex 是独立的球迷数据项目，与 NBA 及各球队没有关联。数据来自 stats.nba.com。")}</footer>
    </>
  );
}
