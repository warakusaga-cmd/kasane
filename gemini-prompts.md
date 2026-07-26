# Kasane 種目ヒーロー画像 — Gemini生成プロンプト集

クロコ（Claude）がプロンプトを用意 → 森田さんがGeminiで生成 → `img/種目名.png` に保存すると、
種目詳細画面が自動で棒人間から画像に差し替わります（`onerror`フォールバック実装済み）。

---

## 使い方（3ステップ）

1. **下の「共通スタイル」＋「種目別アクション」を1つのプロンプトに合体**してGeminiに貼る
   （Geminiアプリ / Google AI Studio / Imagen、どれでもOK）。
2. 生成された画像を **正方形1:1・白背景** でダウンロード。
3. `~/kasane/img/` に **種目名そのままのファイル名**で保存（例：`ラットプルダウン.png`）。
   → 詳細画面をリロードすると自動で表示されます。

> ⚠️ 一貫性のコツ：**共通スタイルの文は毎回まったく同じにする**こと。ここを固定すると、
> 全種目で画風・服の色・背景・アングルが揃った「シリーズもの」に見えます。

---

## 共通スタイル（毎回この塊を先頭に貼る）

```text
A clean modern 3D fitness app illustration, soft matte clay-render style with
rounded friendly shapes. One person, wearing a plain orange athletic top and
medium-gray shorts, light skin-neutral tone. Gym equipment in light gray (#DDE1E7).
Pure flat white background (#FFFFFF), soft top-down studio lighting, subtle contact
shadow under the figure. Full body visible, centered, front three-quarter view.
Friendly, calm, instructional. No text, no numbers, no logos, no watermark,
no extra people. Square 1:1 composition.
Pose / action:
```

この直後に、種目ごとの「アクション1文」を続けます。

---

## 種目別アクション（英文・そのまま追記）

### 胸
- **ベンチプレス** — `lying on a flat bench, pressing a barbell straight up from mid-chest.`
- **ダンベルプレス** — `lying on a flat bench, pressing two dumbbells up above the chest.`
- **インクラインベンチプレス** — `lying on an incline bench set ~30°, pressing a barbell up.`
- **チェストプレス** — `seated at a chest-press machine, pushing two handles forward.`
- **ダンベルフライ** — `lying on a flat bench, arms wide with slight elbow bend holding two dumbbells, opening the chest.`
- **ペックフライ** — `seated at a pec-deck machine, bringing two arm pads together in front of the chest.`
- **ディップス** — `supporting body on parallel bars, torso leaning slightly forward, elbows bent 90°.`

### 背中
- **ラットプルダウン** — `seated at a lat-pulldown machine with thigh pads down, pulling a wide bar down to the collarbone.`
- **懸垂** — `hanging from a pull-up bar with wide overhand grip, chin near the bar.`
- **ベントオーバーロー** — `standing bent forward ~45°, rowing a barbell toward the navel.`
- **ワンハンドダンベルロー** — `one knee and one hand on a bench, rowing a single dumbbell with the other arm.`
- **シーテッドロー** — `seated at a cable row machine, pulling a handle to the stomach, back upright.`
- **デッドリフト** — `standing, lifting a barbell from the floor, flat back, hips hinged.`
- **シュラッグ** — `standing, holding two dumbbells at the sides, shrugging shoulders straight up.`

### 肩
- **ショルダープレス** — `seated, pressing two dumbbells straight overhead from shoulder height.`
- **サイドレイズ** — `standing, raising two light dumbbells out to the sides to shoulder height.`
- **リアレイズ** — `bent forward ~45°, raising two dumbbells out to the sides for the rear delts.`
- **フロントレイズ** — `standing, raising a dumbbell straight in front to shoulder height.`
- **アーノルドプレス** — `seated, rotating dumbbells while pressing them overhead.`
- **フェイスプル** — `standing at a cable, pulling a rope toward the face, elbows high.`

### 腕
- **アームカール** — `standing, curling two dumbbells up toward the shoulders, elbows fixed at sides.`
- **ハンマーカール** — `standing, curling two dumbbells with a neutral (hammer) grip.`
- **トライセプスエクステンション** — `standing, holding one dumbbell overhead with both hands, lowering it behind the head.`
- **ケーブルプレスダウン** — `standing at a cable, pushing a bar down by extending the elbows.`
- **キックバック** — `bent forward, upper arm parallel to torso, extending a dumbbell back.`

### 脚
- **スクワット** — `standing with a barbell across the upper back, squatting until thighs are parallel.`
- **ゴブレットスクワット** — `standing, holding one dumbbell vertically at the chest, squatting down.`
- **レッグプレス** — `seated in a leg-press machine, pushing the platform with both feet.`
- **レッグエクステンション** — `seated at a leg-extension machine, straightening the knees against the pad.`
- **レッグカール** — `lying prone on a leg-curl machine, bending the knees to curl the pad up.`
- **ランジ** — `standing, taking a long step forward into a lunge, back knee near the floor.`
- **ヒップスラスト** — `upper back on a bench, barbell across the hips, thrusting the hips up.`
- **カーフレイズ** — `standing on the edge of a step, rising up onto the toes.`

### 腹
- **腹筋ローラー** — `kneeling, rolling an ab-wheel forward on the floor, body extended.`
- **プランク** — `holding a forearm plank position, body in a straight line.`
- **レッグレイズ** — `lying on the back, raising straight legs up toward the ceiling.`
- **クランチ** — `lying on the back, knees bent, curling the upper body up.`
- **ロシアンツイスト** — `seated, leaning back with feet up, twisting the torso side to side.`

### 有酸素
- **ランニング** — `running on a treadmill, mid-stride.`
- **エアロバイク** — `pedaling on a stationary exercise bike.`
- **ウォーキング** — `walking on a treadmill at an easy pace.`
- **縄跳び** — `jumping rope, both feet off the ground.`

---

## ここに無い種目

同じ要領で、共通スタイルの後ろに「その種目の動作」を1文（英語）で足すだけ。
迷ったらクロコに「◯◯のアクション文だけ書いて」と言ってください。すぐ出します。

## バリエーション種目の画像を使い回す

似た動作はファイルをコピーで流用できます。例：

```bash
cd ~/kasane/img
cp ベンチプレス.png ナローベンチプレス.png       # 手幅違い
cp サイドレイズ.png ケーブルサイドレイズ.png       # ダンベル→ケーブル
cp ラットプルダウン.png ストレートアームプルダウン.png
```
