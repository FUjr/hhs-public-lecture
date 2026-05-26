function normalizeText(text) {
  return String(text || "")
    .replace(/[？?，“”‘’、；：:\s]/g, "")
    .replace(/[，。！？.!]/g, "")
    .toLowerCase()
    .trim();
}

function containsAny(text, words) {
  return words.some((word) => word && text.includes(word));
}

export function matchPresetAnswer(question, presets = []) {
  const normalized = normalizeText(question);
  if (!normalized) {
    return null;
  }

  let best = null;
  let bestScore = 0;
  for (const preset of presets) {
    const presetQuestion = normalizeText(preset.question);
    if (presetQuestion && (normalized === presetQuestion || normalized.includes(presetQuestion) || presetQuestion.includes(normalized))) {
      return preset;
    }
    const score = (preset.keywords || []).reduce((total, keyword) => {
      return normalizeText(keyword) && normalized.includes(normalizeText(keyword)) ? total + 1 : total;
    }, 0);
    if (score > bestScore) {
      best = preset;
      bestScore = score;
    }
  }
  return bestScore >= 2 ? best : null;
}

export function buildFallbackAnswer(question, lesson) {
  const preset = matchPresetAnswer(question, lesson.presets);
  if (preset) {
    return {
      answer: varyPresetAnswer(preset.answer),
      source: "preset",
      matchedTitle: preset.title || "",
    };
  }

  const title = lesson.title || "本课";
  const core = lesson.coreStatement || lesson.aiStudentPrompt || "课文的核心观点";
  return {
    answer: `这个问题可以继续往${title}的关键内容里想。先抓住课文中的主要意象、作者态度和写作手法，再追问它们共同指向什么。结合本课来看，答案不应只停留在内容复述上，还要回到“${core}”所体现的人格或思想价值。`,
    source: "local",
    matchedTitle: "",
  };
}

export function buildReflectionFeedback(text, lesson) {
  const cleaned = String(text || "").trim();
  const core = lesson.coreStatement || lesson.aiStudentPrompt || "课文中的核心观点";
  if (!cleaned) {
    return {
      feedback: "可以先让学生用一句话表明立场，再补充一个具体经历或理由，最后回到课文中的关键词。",
      followUp: "请先用一句话表明你的立场，再补充一个生活中的例子。",
    };
  }

  let feedback = "这个回答已经开始把课文和现实联系起来了。";
  if (containsAny(cleaned, ["环境", "影响", "近墨者黑", "带偏"])) {
    feedback = `你抓住了环境影响这个现实问题。课文的价值不是否认环境复杂，而是提醒人在受到影响时仍要保持判断，努力接近“${core}”所指向的状态。`;
  } else if (containsAny(cleaned, ["坚持", "原则", "底线", "拒绝", "不盲从", "独立"])) {
    feedback = `你抓住了坚守原则这个关键点。真正可贵的不是在轻松环境里说正确的话，而是在压力、诱惑或从众面前仍能守住自己的判断，这正能回扣“${core}”。`;
  } else if (containsAny(cleaned, ["两种", "辩证", "一方面", "另一方面", "既", "也"])) {
    feedback = `这种辩证看法比较完整：环境确实会影响人，但人也不是完全被动的。继续推进时，可以把重点落到一个人怎样选择环境、怎样守住内心。`;
  }

  return {
    feedback,
    followUp: buildFollowUp(cleaned),
  };
}

export function buildFollowUpResponse(text, lesson) {
  const cleaned = String(text || "").trim();
  const core = lesson.coreStatement || "课文核心观点";
  if (!cleaned) {
    return "可以先让学生用一句话回应这个追问，再补充一个具体理由。";
  }
  if (containsAny(cleaned, ["长期", "判断力", "习惯", "一直", "平时"])) {
    return `这个回应把理解从一次选择推进到了长期修养。可以概括为：真正的品格不是偶尔做到，而是在复杂情境中反复守住判断和底线，这样就能更深入地理解“${core}”。`;
  }
  if (containsAny(cleaned, ["勇气", "敢", "拒绝", "说不"])) {
    return "你抓住了现实中的难处：很多时候坚持需要勇气。还可以继续思考，勇气怎样变成稳定的原则和习惯。";
  }
  if (containsAny(cleaned, ["朋友", "圈子", "远离", "选择环境", "主动"])) {
    return "这个回答把人的主动性说出来了。选择环境不是逃避现实，而是在知道环境会影响人的前提下，尽量让自己接近更好的力量，同时保留自己的判断。";
  }
  return "这个回应可以作为继续讨论的起点。再补上一个具体情境，说明人在压力、诱惑或从众心理面前到底怎样做，观点会更有说服力。";
}

function buildFollowUp(text) {
  if (containsAny(text, ["两种", "辩证", "既", "也", "一方面", "另一方面", "主动选择"])) {
    return "如果环境会影响人，而人也能作选择，你认为“选择环境”和“守住内心”哪一步更关键？";
  }
  if (containsAny(text, ["环境", "影响", "近墨者黑", "带偏", "很难"])) {
    return "当环境确实会影响人时，一个人可以靠哪些具体做法减少被“染”的可能？";
  }
  if (containsAny(text, ["坚持", "原则", "底线", "独立", "不盲从", "拒绝"])) {
    return "把你的例子再推进一步：这种坚守靠的是一时勇气，还是长期形成的判断力？";
  }
  return "请把你的观点和课文中的一句话连起来，再说明这句话为什么能支持你的看法。";
}

function varyPresetAnswer(answer) {
  const sentences = String(answer || "").match(/[^。！？!?]+[。！？!?]?/g) || [];
  if (sentences.length < 3) {
    return answer;
  }
  return `${sentences[0]}${sentences.slice(1).join("")}`;
}
