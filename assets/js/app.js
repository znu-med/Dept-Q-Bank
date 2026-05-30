}
    });
    this.config.subjects.forEach(sub => {
      if (sub.label.toLowerCase().includes(q)) {
        found.push({ type: 'subject', label: sub.label, sub: 'Subject', nav: 'dashboard', params: {} });
      }
    });
    Storage.getIncorrect().forEach(iq => {
      if (iq.question.toLowerCase().includes(q)) {
        found.push({ type: 'question', label: iq.question, sub: ${iq.module} · ${iq.subject}, nav: 'review', params: {} });
      }
    });

    if (found.length === 0) {
      container.innerHTML = <p class="search-hint">No results for "<strong>${query}</strong>".</p>;
      return;
    }
    container.innerHTML = found.slice(0, 30).map(r => 
      <div class="search-result-item" data-nav="${r.nav}" data-params='${JSON.stringify(r.params)}'>
        <span class="search-result-item__type">${r.type}</span>
        <div>
          <div class="search-result-item__label">${r.label}</div>
          <div class="search-result-item__sub">${r.sub}</div>
        </div>
      </div>).join('');
  },

  // ─── Exam start helper ───────────────────────────────────────────────────

  async _startExam(params) {
    if (params.retryIncorrectOnly) {
      const all = Storage.getIncorrect().filter(
        q => q.module === params.moduleId &&
             q.examType === params.examType &&
             q.subject === params.subject &&
             q.subSubject === params.subSubject
      );
      if (all.length === 0) {
        UI.toast('No incorrect questions to retry.', 'info');
        return false;
      }
      ExamEngine.config = {
        module:            params.moduleId,
        examType:          params.examType,
        subject:           params.subject,
        subSubject:        params.subSubject,
        immediateFeedback: params.immediateFeedback ?? false,
        randomize:         params.randomize ?? true,
      };
      ExamEngine.questions = params.randomize ? ExamEngine._shuffle([...all]) : all;
      ExamEngine.state = {
        currentIndex: 0,
        answers: {},
        flagged: new Set(),
        startTime: Date.now(),
        endTime: null,
        submitted: false,
      };
      return true;
    }

    const count = await ExamEngine.init({
      module:            params.moduleId,
      examType:          params.examType,
      subject:           params.subject,
      subSubject:        params.subSubject,
      immediateFeedback: params.immediateFeedback ?? false,
      randomize:         params.randomize ?? false,
    });

    if (count === 0) {
      UI.toast('No questions available for this sub-subject yet.', 'info');
      return false;
    }
    return true;
  },

  // ─── Config / data loaders ────────────────────────────────────────────────

  async _loadConfig() {
    const res = await fetch('config/modules.json');
    if (!res.ok) throw new Error(HTTP ${res.status});
    return await res.json();
  },

  async _getQuestionCount(mod, examType, subject, subSubject) {
    const path = data/${mod.dataPath}/${examType}/${subject}/${subSubject}.json;
    try {
      const res = await fetch(path);
      if (!res.ok) return 0;
      const data = await res.json();
      return Array.isArray(data.questions) ? data.questions.length : 0;
    } catch { return 0; }
  },

  _getModule(id) {
    return this.config?.modules?.find(m => m.id === id) ?? null;
  },
};

document.addEventListener('DOMContentLoaded', () => App.init());
