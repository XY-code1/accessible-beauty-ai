import { useCallback, useEffect, useRef, useState } from "react";
import EyelinerPractice, { EyeIcon } from "./EyelinerPractice";
import { publicFeedbackUrl } from "./feedback";

function route() {
  return /^#\/eyeliner(?:\/|$)/.test(location.hash) ? "eyeliner" : "home";
}

export default function App() {
  const [page, setPage] = useState(route);
  const feedbackUrl = publicFeedbackUrl(import.meta.env.VITE_FEEDBACK_URL);
  const engaged = useRef(false);
  const onEngagementChange = useCallback((active: boolean) => {
    engaged.current = active;
  }, []);

  useEffect(() => {
    const navigate = () => {
      const next = route();
      if (
        page === "eyeliner" &&
        next === "home" &&
        engaged.current &&
        !window.confirm("离开本次练习？摄像头将关闭，本次照片和进度将清除。")
      ) {
        history.replaceState(null, "", "#/eyeliner");
        return;
      }
      const hash = next === "eyeliner" ? "#/eyeliner" : "#/";
      if (location.hash !== hash) history.replaceState(null, "", hash);
      setPage(next);
    };
    navigate();
    window.addEventListener("hashchange", navigate);
    return () => window.removeEventListener("hashchange", navigate);
  }, [page]);

  useEffect(() => {
    window.scrollTo(0, 0);
    document.querySelector<HTMLElement>("h1")?.focus({ preventScroll: true });
  }, [page]);

  if (page === "eyeliner")
    return <EyelinerPractice onEngagementChange={onEngagementChange} />;
  return (
    <div className="app-shell home-shell">
      <header className="header">
        <a className="brand" href="#/" aria-label="无界美妆首页">
          <span className="brand-icon">
            <EyeIcon />
          </span>
          <span>
            无界美妆<small>BEAUTY WITHOUT BARRIERS</small>
          </span>
        </a>
        <span className="edition">妆容工作台</span>
      </header>
      <main>
        <section className="home-intro">
          <p className="eyebrow">把每一步，变得容易一点</p>
          <h1 tabIndex={-1}>今天，从哪一步开始？</h1>
          <p>
            选一个部位，跟着自己的节奏练习。
            <br />
            从看懂形状，到亲手完成。
          </p>
        </section>
        <section className="makeup-grid" aria-label="选择练习部位">
          <article className="makeup-module available">
            <div className="module-art">
              <EyeIcon large />
            </div>
            <div>
              <span className="module-status">现在可以练习</span>
              <h2>眼线</h2>
              <p>单侧自然眼线 · 实时参考轮廓与分步指引</p>
              <a className="primary" href="#/eyeliner">
                开始眼线练习 <span aria-hidden="true">↗</span>
              </a>
              <small>方向检查为实验功能，真人效果仍在验证。</small>
            </div>
          </article>
          {[
            ["底妆", "探索均匀、自然的底妆"],
            ["眉妆", "了解眉形与填充方向"],
            ["眼影", "理解颜色的落点与层次"],
            ["唇妆", "练习轮廓与颜色表达"],
          ].map(([name, description]) => (
            <article className="makeup-module upcoming" key={name}>
              <span className="module-status">尚未开放</span>
              <h2>{name}</h2>
              <p>{description}</p>
              <small>正在规划中，暂不提供练习与检查。</small>
            </article>
          ))}
        </section>
        <aside className="home-note">
          <strong>在你的节奏里，也在你的设备里。</strong>
          <p>
            进入练习后，由你开启摄像头。本次照片只在会话内处理，结束或离开即清除。
          </p>
        </aside>
        <section className="test-invite" aria-labelledby="test-invite-title">
          <p className="eyebrow">公开测试说明</p>
          <h2 id="test-invite-title">参与测试</h2>
          <ul>
            <li>当前是眼线功能测试版。</li>
            <li>建议使用最新版 iOS Safari。</li>
            <li>摄像头画面默认只在本机处理。</li>
            <li>不会自动上传人脸图片、视频、音频或面部关键点。</li>
            <li>测试结束后可以填写反馈。</li>
          </ul>
          {feedbackUrl ? (
            <a
              className="secondary test-feedback-link"
              href={feedbackUrl}
              target="_blank"
              rel="noreferrer"
            >
              填写测试反馈
            </a>
          ) : (
            <p className="feedback-unavailable">反馈问卷配置后开放。</p>
          )}
        </section>
      </main>
      <footer>
        <span>BEAUTY, AT YOUR OWN PACE.</span>
        <p>从单侧眼线开始，逐步探索全妆辅助。</p>
      </footer>
    </div>
  );
}
