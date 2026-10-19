// Поле «О себе»: текст пишет бесплатная нейросеть по остальным разделам формы.
// Пока пользователь не правил поле сам, запрос уходит после паузы в наборе.
// Бесплатный доступ отвечает примерно раз в полминуты — до этого в поле черновик.
(() => {
    const form = document.getElementById("resume-form");
    const summary = document.getElementById("summary");
    const button = document.getElementById("generate-summary");
    const status = document.getElementById("summary-status");
    if (!form || !summary || !button || !form.dataset.summaryUrl) return;

    const DEBOUNCE_MS = 800;
    let timer = null;
    let retryTimer = null;
    let controller = null;
    let seq = 0;

    if (summary.value.trim()) summary.dataset.manual = "1";

    function grow(textarea) {
        textarea.style.height = "auto";
        textarea.style.height = `${textarea.scrollHeight + 2}px`;
    }

    function shouldAuto() {
        return summary.dataset.manual !== "1" && document.activeElement !== summary;
    }

    function apply(text) {
        summary.dataset.writing = "1";
        summary.value = text;
        summary.dataset.manual = "0";
        summary.dataset.auto = text ? "1" : "0";
        summary.dataset.writing = "0";
        grow(summary);
    }

    async function generate(interactive) {
        const requestId = ++seq;
        if (controller) controller.abort();
        controller = new AbortController();

        const data = new FormData(form);
        data.delete("photo");
        if (interactive) {
            button.disabled = true;
            status.textContent = "Нейросеть пишет текст…";
        } else if (!summary.value.trim()) {
            status.textContent = "Нейросеть пишет текст…";
        }

        try {
            const response = await fetch(form.dataset.summaryUrl, {
                method: "POST",
                body: data,
                signal: controller.signal,
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const payload = await response.json();
            if (requestId !== seq || summary.dataset.manual === "1") return;

            if (!payload.summary) {
                if (summary.dataset.auto === "1") apply("");
                status.textContent = payload.message || "";
                return;
            }
            apply(payload.summary);
            if (payload.source === "model") {
                status.textContent = "Текст написала нейросеть. Его можно отредактировать.";
            } else if (payload.message) {
                status.textContent = payload.message;
            } else {
                status.textContent = "Текст составлен по заполненным разделам. Его можно отредактировать.";
            }
            if (payload.source === "draft" && payload.retry_after) {
                scheduleRetry(payload.retry_after);
            }
        } catch (error) {
            if (error.name === "AbortError") return;
            if (requestId !== seq) return;
            if (interactive) status.textContent = "Не удалось составить текст. Попробуйте ещё раз.";
        } finally {
            if (requestId === seq) button.disabled = false;
        }
    }

    function scheduleRetry(seconds) {
        clearTimeout(retryTimer);
        const delay = Math.min(Math.max(seconds, 1), 90) * 1000;
        retryTimer = setTimeout(() => {
            if (summary.dataset.manual === "1") return;
            generate(false);
        }, delay);
    }

    function schedule() {
        if (!shouldAuto()) return;
        clearTimeout(retryTimer);
        clearTimeout(timer);
        timer = setTimeout(() => generate(false), DEBOUNCE_MS);
    }

    summary.addEventListener("input", () => {
        if (summary.dataset.writing === "1") return;
        summary.dataset.manual = summary.value.trim() ? "1" : "0";
        if (summary.dataset.manual === "1") {
            clearTimeout(retryTimer);
            return;
        }
        schedule();
    });
    summary.addEventListener("blur", () => {
        if (summary.dataset.manual !== "1") schedule();
    });

    form.addEventListener("input", (event) => {
        if (event.target === summary) return;
        schedule();
    });
    form.addEventListener("change", (event) => {
        if (event.target === summary) return;
        schedule();
    });
    form.addEventListener("click", (event) => {
        if (event.target.closest("[data-remove-entry]")) schedule();
    });

    button.addEventListener("click", () => {
        summary.dataset.manual = "0";
        generate(true);
    });

    if (shouldAuto()) schedule();
})();
