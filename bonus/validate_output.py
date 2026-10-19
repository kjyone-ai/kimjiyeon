"""LLM 답변 초안 자동 검사기 (수강생 문의 답변 3단 형식용).

검사 항목
  1. 형식: ① 답변 초안 / ② 근거 규정 / ③ 확인 필요 항목 3단 존재 여부
  2. 채널: 카카오톡이면 ① 답변 초안 문장 수 제한(기본 5문장)
  3. 근거: ②에 조항 번호가 있고, 그 조항이 규정 시트에 실제로 존재하는지
  4. 금액 환각: ①의 금액이 (결제 금액 × 규정 비율)로 계산 가능한 값인지
  5. 금지 표현: 담당자 권한 밖 약속, 규정에 없는 절차 표현

사용법:
    python3 bonus/validate_output.py <답변파일> --paid 600000 [--kakao] [--max-sentences 5]
                                     [--policy templates/policy_sheet.md]
"""
import argparse
import re
import sys
from fractions import Fraction

SECTIONS = ["① 답변 초안", "② 근거 규정", "③ 확인 필요 항목"]
FORBIDDEN = ["예외적으로", "특별히", "마이페이지", "영업일 내 입금", "무료 재수강", "보장"]

MONEY_RE = re.compile(r"(\d+)\s*만\s*원|(\d{1,3}(?:,\d{3})+|\d{4,})\s*원")
ARTICLE_RE = re.compile(r"제\s*(\d+)\s*조")
FRACTION_RE = re.compile(r"(\d+)\s*/\s*(\d+)")


def extract_money(text):
    found = set()
    for man, won in MONEY_RE.findall(text):
        found.add(int(man) * 10000 if man else int(won.replace(",", "")))
    return found


def split_sections(text):
    positions = sorted((text.find(s), s) for s in SECTIONS if s in text)
    parts = {}
    for i, (pos, name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        parts[name] = text[pos + len(name):end].strip()
    return parts


def count_sentences(text):
    body = re.sub(r"📌.*", "", text)
    return len([s for s in re.split(r"(?<=[.!?요다])\s+|\n+", body) if s.strip()])


def validate(answer, policy, paid, kakao, max_sentences):
    errors = []
    parts = split_sections(answer)
    missing = [s for s in SECTIONS if s not in parts]
    if missing:
        errors.append(f"[형식] 누락된 칸: {', '.join(missing)}")
    draft = parts.get("① 답변 초안", "")
    basis = parts.get("② 근거 규정", "")

    if kakao:
        n = count_sentences(draft)
        if n > max_sentences:
            errors.append(f"[채널] 카카오톡 {max_sentences}문장 초과: {n}문장")

    policy_articles = set(ARTICLE_RE.findall(policy))
    cited = set(ARTICLE_RE.findall(basis))
    if not cited:
        errors.append("[근거] ② 근거 규정에 조항 번호(제○조)가 없음")
    for a in sorted(cited - policy_articles, key=int):
        errors.append(f"[환각 의심] 규정 시트에 없는 조항 인용: 제{a}조")

    if paid:
        ratios = {Fraction(1)} | {Fraction(int(a), int(b)) for a, b in FRACTION_RE.findall(policy) if int(b)}
        allowed = {int(paid * r) for r in ratios}
        for amount in sorted(extract_money(draft)):
            if amount not in allowed:
                errors.append(f"[환각 의심] 규정으로 계산되지 않는 금액: {amount:,}원 "
                              f"(허용: {', '.join(f'{x:,}' for x in sorted(allowed))})")

    for word in FORBIDDEN:
        if word in draft:
            errors.append(f"[금지 표현] 권한 밖 약속/규정 밖 절차 의심: '{word}'")
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("answer")
    ap.add_argument("--policy", default="templates/policy_sheet.md")
    ap.add_argument("--paid", type=int, default=0, help="결제 금액(원). 주면 금액 환각 검사")
    ap.add_argument("--kakao", action="store_true", help="카카오톡 채널 문장 수 검사")
    ap.add_argument("--max-sentences", type=int, default=5)
    args = ap.parse_args()

    with open(args.answer, encoding="utf-8") as f:
        answer = f.read()
    with open(args.policy, encoding="utf-8") as f:
        policy = f.read()

    errors = validate(answer, policy, args.paid, args.kakao, args.max_sentences)
    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    print("PASS")


if __name__ == "__main__":
    main()
