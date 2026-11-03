import unittest

from visual_vocabulary import classify_fit_vocabulary, match_visual_vocabulary


class VisualVocabularyTests(unittest.TestCase):
    def test_learns_character_verbs_by_action_family(self):
        cases = (
            ("뒤쫓다", "뒤를 따라 쫓다", "running"),
            ("후려치다", "팔을 휘둘러 힘껏 치다", "fighting"),
            ("뒤적이다", "물건을 들추며 찾다", "investigating"),
            ("건네받다", "다른 사람에게 물건을 받아 들다", "interacting"),
            ("수군거리다", "작은 목소리로 이야기하다", "talking"),
            ("어루만지다", "손으로 부드럽게 쓰다듬다", "helping"),
        )
        for word, meaning, expected_tag in cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {
                        "word": word,
                        "meaning": meaning,
                        "pos_group": "동사",
                    }
                )

                self.assertEqual(result["primary_role"], "action")
                self.assertTrue(result["usable_for_image"])
                self.assertIn(expected_tag, result["action_tags"])

    def test_marks_only_solo_motion_families_as_solo_actions(self):
        solo_cases = (
            ("걷다", "다리를 움직여 앞으로 가다"),
            ("뛰어오르다", "몸을 위로 올려 도약하다"),
            ("마법", "주문을 외워 마법을 부리다"),
            ("뒤적이다", "물건을 들추며 찾다"),
            ("손을 흔들다", "손을 흔들어 인사하다"),
        )
        for word, meaning in solo_cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )
                self.assertTrue(result["solo_action"])

        non_solo_cases = (
            ("맞붙다", "서로 상대하여 겨루다"),
            ("도와주다", "다른 사람을 도와주다"),
            ("건네받다", "다른 사람에게 물건을 받아 들다"),
            ("대화하다", "다른 사람과 이야기를 나누다"),
        )
        for word, meaning in non_solo_cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )
                self.assertFalse(result["solo_action"])

    def test_expanded_solo_verbs_keep_their_motion_family(self):
        cases = (
            ("기어가다", "바닥을 따라 천천히 기어가다", "crawling", "journey"),
            ("질주하다", "길을 따라 빠르게 질주하다", "running", "journey"),
            ("뛰어내리다", "바위에서 아래로 뛰어내리다", "jumping", "jump"),
            ("둘러보다", "주변을 천천히 둘러보다", "investigating", "investigate"),
            ("손짓하다", "멀리서 손짓하다", "waving", "wave"),
        )
        for word, meaning, tag, animation in cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )
                self.assertIn(tag, result["action_tags"])
                self.assertEqual(
                    result["action_semantics"]["animation_action"], animation
                )
                self.assertTrue(result["solo_action"])

    def test_climbing_words_are_not_classified_as_running(self):
        for word, meaning in (
            ("기어가다", "바닥을 따라 천천히 기어가다"),
            ("기어오르다", "바위 벽을 손과 발로 기어오르다"),
            ("오르다", "산길을 따라 위로 오르다"),
        ):
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )

                self.assertNotIn("running", result["action_tags"])
                self.assertIn(
                    "crawling" if word == "기어가다" else "climbing",
                    result["action_tags"],
                )
                self.assertTrue(result["solo_action"])
                self.assertEqual(
                    result["action_semantics"]["interaction_kind"],
                    "crawl" if word == "기어가다" else "climb",
                )

    def test_stationary_single_character_verbs_are_action_classified(self):
        cases = (
            ("멈추다", "걸음을 멈추다", "stopping", "stop"),
            ("방향을 바꾸다", "성문 쪽으로 방향을 바꾸다", "turning", "turn_in_place"),
            ("앉다", "나무 아래에 앉다", "sitting", "sit"),
            ("일어서다", "자리에서 일어서다", "standing", "stand"),
        )
        for word, meaning, tag, interaction_kind in cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )

                self.assertEqual(result["primary_role"], "action")
                self.assertTrue(result["usable_for_image"])
                self.assertIn(tag, result["action_tags"])
                self.assertEqual(
                    result["action_semantics"]["interaction_kind"],
                    interaction_kind,
                )

                if interaction_kind in {"sit", "stand"}:
                    self.assertTrue(result["solo_action"])
                    self.assertEqual(
                        result["action_semantics"]["animation_action"],
                        interaction_kind,
                    )

    def test_learns_environmental_verb_as_effect_not_character_motion(self):
        result = classify_fit_vocabulary(
            {
                "word": "서리다",
                "meaning": "차가운 기운이 물방울로 엉기다",
                "pos_group": "동사",
            }
        )

        self.assertEqual(result["primary_role"], "environment_effect")
        self.assertTrue(result["usable_for_image"])
        self.assertEqual(result["action_tags"], [])
        self.assertIn("mist", result["effect_tags"])
        self.assertEqual(
            result["action_semantics"]["motion_mode"],
            "environmental",
        )
        self.assertEqual(result["action_semantics"]["participant_count"], 0)

    def test_handoff_requires_a_stationary_receiver_and_giver(self):
        result = classify_fit_vocabulary(
            {
                "word": "건네받다",
                "meaning": "다른 사람에게 물건을 받아 들다",
                "pos_group": "동사",
            }
        )

        semantics = result["action_semantics"]
        self.assertEqual(semantics["motion_mode"], "stationary")
        self.assertEqual(semantics["participant_count"], 2)
        self.assertTrue(semantics["requires_partner"])
        self.assertEqual(semantics["interaction_kind"], "handoff_receive")
        self.assertEqual(semantics["subject_role"], "receiver")
        self.assertEqual(semantics["partner_role"], "giver")

    def test_locomotion_and_stationary_verbs_keep_distinct_motion_modes(self):
        chasing = classify_fit_vocabulary(
            {
                "word": "뒤쫓다",
                "meaning": "뒤를 따라 빠르게 쫓다",
                "pos_group": "동사",
            }
        )
        searching = classify_fit_vocabulary(
            {
                "word": "뒤적이다",
                "meaning": "물건을 들추며 찾다",
                "pos_group": "동사",
            }
        )

        self.assertEqual(chasing["action_semantics"]["motion_mode"], "locomotion")
        self.assertEqual(searching["action_semantics"]["motion_mode"], "stationary")

    def test_target_and_partner_verbs_cannot_be_solo_actions(self):
        cases = (
            ("뒤쫓다", "달아나는 괴물을 뒤쫓다"),
            ("싸우다", "용과 싸우다"),
            ("건네받다", "친구에게 열쇠를 건네받다"),
        )
        for word, meaning in cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )

                semantics = result["action_semantics"]
                self.assertFalse(result["solo_action"])
                self.assertTrue(semantics["requires_partner"])
                self.assertGreaterEqual(semantics["participant_count"], 2)

    def test_targeted_strike_does_not_require_a_second_character(self):
        aiming = classify_fit_vocabulary(
            {
                "word": "겨누다",
                "meaning": "활이나 총을 목표물 쪽으로 향하다",
                "pos_group": "동사",
            }
        )["action_semantics"]
        duel = classify_fit_vocabulary(
            {
                "word": "맞붙다",
                "meaning": "서로 상대하여 겨루다",
                "pos_group": "동사",
            }
        )["action_semantics"]

        self.assertEqual(aiming["participant_count"], 1)
        self.assertFalse(aiming["requires_partner"])
        self.assertTrue(aiming["requires_object"])
        self.assertEqual(aiming["object_role"], "weapon")
        self.assertTrue(aiming["requires_target"])
        self.assertEqual(duel["participant_count"], 2)
        self.assertTrue(duel["requires_partner"])

    def test_receive_food_requires_giver_and_food_prop(self):
        semantics = classify_fit_vocabulary(
            {
                "word": "받아먹다",
                "meaning": "남이 주는 음식을 받아서 먹다",
                "pos_group": "동사",
            }
        )["action_semantics"]

        self.assertEqual(semantics["participant_count"], 2)
        self.assertTrue(semantics["requires_partner"])
        self.assertTrue(semantics["requires_object"])
        self.assertEqual(semantics["object_role"], "food")
        self.assertEqual(semantics["body_focus"], "hands_and_face")

    def test_newly_learned_verbs_cover_motion_and_environment(self):
        cases = (
            ("가다듬다", "마음과 자세를 바로잡다", "stationary", "self_adjust"),
            ("설치다", "조급하게 이리저리 움직이다", "locomotion", "move_erratically"),
            ("걷히다", "안개가 흩어져 없어지다", "environmental", "weather_clearing"),
            ("킁킁거리다", "코로 냄새를 반복해서 맡다", "stationary", "sniff"),
        )
        for word, meaning, motion_mode, interaction_kind in cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "동사"}
                )

                self.assertTrue(result["usable_for_image"])
                self.assertEqual(
                    result["action_semantics"]["motion_mode"],
                    motion_mode,
                )
                self.assertEqual(
                    result["action_semantics"]["interaction_kind"],
                    interaction_kind,
                )

    def test_semantics_include_body_path_and_time_features(self):
        semantics = classify_fit_vocabulary(
            {
                "word": "뒤쫓다",
                "meaning": "뒤를 따라 빠르게 쫓다",
                "pos_group": "동사",
            }
        )["action_semantics"]

        self.assertEqual(semantics["body_focus"], "full_body")
        self.assertEqual(semantics["path_pattern"], "pursuit")
        self.assertEqual(semantics["temporal_pattern"], "continuous")
        self.assertEqual(semantics["directionality"], "toward_target")

    def test_unmapped_abstract_verb_stays_non_visual(self):
        result = classify_fit_vocabulary(
            {
                "word": "안되다",
                "meaning": "일이 좋게 이루어지지 않다",
                "pos_group": "동사",
            }
        )

        self.assertEqual(result["primary_role"], "non_visual")
        self.assertFalse(result["usable_for_image"])

    def test_matches_learned_running_verb_in_an_inflected_sentence(self):
        document = classify_fit_vocabulary(
            {
                "word": "뒤쫓다",
                "meaning": "뒤를 따라 빠르게 쫓다",
                "pos_group": "동사",
            }
        )
        document.update({"fit_score": 90, "enabled": True})

        context = match_visual_vocabulary(
            "용사는 달아나는 괴물을 뒤쫓아 숲길로 향했어요.",
            [document],
        )

        self.assertEqual(context["matched_words"], ["뒤쫓다"])
        self.assertIn("running", context["action_tags"])
        self.assertEqual(context["action_semantics"]["source_word"], "뒤쫓다")
        self.assertEqual(context["action_semantics"]["motion_mode"], "locomotion")

    def test_match_propagates_handoff_participant_constraints(self):
        document = classify_fit_vocabulary(
            {
                "word": "건네받다",
                "meaning": "다른 사람에게 물건을 받아 들다",
                "pos_group": "동사",
            }
        )
        document.update({"fit_score": 95, "enabled": True})

        context = match_visual_vocabulary(
            "하나는 친구에게 반짝이는 열쇠를 건네받았어요.",
            [document],
        )

        self.assertEqual(context["action_semantics"]["source_word"], "건네받다")
        self.assertTrue(context["action_semantics"]["requires_partner"])
        self.assertEqual(context["action_semantics"]["participant_count"], 2)

    def test_matches_new_irregular_verb_conjugations(self):
        cases = (
            ("걷히다", "안개가 천천히 걷혔다."),
            ("겨누다", "궁수가 과녁을 정확히 겨눴다."),
            ("설치다", "아이는 마당을 부산하게 설쳤다."),
        )
        for word, sentence in cases:
            with self.subTest(word=word):
                document = classify_fit_vocabulary(
                    {"word": word, "meaning": sentence, "pos_group": "동사"}
                )
                document.update({"fit_score": 90, "enabled": True})

                context = match_visual_vocabulary(sentence, [document])

                self.assertEqual(context["matched_words"], [word])
                self.assertEqual(
                    context["action_semantics"]["source_word"],
                    word,
                )

    def test_classifies_korean_background_word(self):
        result = classify_fit_vocabulary(
            {
                "word": "항구",
                "meaning": "배가 머무는 바닷가 장소",
                "pos_group": "명사",
            }
        )

        self.assertEqual(result["primary_role"], "place")
        self.assertTrue(result["usable_for_image"])
        self.assertIn("adventure_harbor", result["background_keys"])

    def test_classifies_environment_effect(self):
        result = classify_fit_vocabulary(
            {
                "word": "회오리",
                "meaning": "바람이 한곳에서 빙빙 도는 현상",
                "pos_group": "명사",
            }
        )

        self.assertEqual(result["primary_role"], "environment_effect")
        self.assertTrue(result["usable_for_image"])
        self.assertIn("whirlwind", result["effect_tags"])
        self.assertTrue(result["evidence"])

    def test_learns_new_place_prop_weather_and_emotion_words(self):
        cases = (
            ("과수원", "과실나무를 심은 밭", "place", "nature_pond"),
            ("광주리", "대나무로 엮어 만든 그릇", "object", "woven_basket"),
            ("노을", "해 질 무렵 붉게 물든 하늘", "environment_effect", "sunset_glow"),
            ("반가움", "반가운 감정이나 마음", "emotion", "joyful"),
        )
        tag_fields = {
            "place": "background_keys",
            "object": "prop_tags",
            "environment_effect": "effect_tags",
            "emotion": "emotion_tags",
        }
        for word, meaning, role, expected_tag in cases:
            with self.subTest(word=word):
                result = classify_fit_vocabulary(
                    {"word": word, "meaning": meaning, "pos_group": "명사"}
                )

                self.assertEqual(result["primary_role"], role)
                self.assertTrue(result["usable_for_image"])
                self.assertIn(expected_tag, result[tag_fields[role]])

    def test_adverb_modifies_motion_without_inventing_action_semantics(self):
        result = classify_fit_vocabulary(
            {
                "word": "슬며시",
                "meaning": "행동이 은근하고 천천히",
                "pos_group": "부사",
            }
        )

        self.assertTrue(result["usable_for_image"])
        self.assertIn("slow_subtle", result["motion_modifier_tags"])
        self.assertEqual(result["action_semantics"], {})

    def test_matches_multiple_visual_word_types_in_one_scene(self):
        sources = (
            ("과수원", "과실나무를 심은 밭", "명사"),
            ("광주리", "대나무로 엮은 그릇", "명사"),
            ("슬며시", "행동이 은근하고 천천히", "부사"),
            ("방긋", "소리 없이 가볍게 웃는 모양", "부사"),
        )
        documents = []
        for word, meaning, pos in sources:
            document = classify_fit_vocabulary(
                {"word": word, "meaning": meaning, "pos_group": pos}
            )
            document.update({"fit_score": 90, "enabled": True})
            documents.append(document)

        context = match_visual_vocabulary(
            "아이는 과수원에서 광주리를 들고 슬며시 다가와 방긋 웃었어요.",
            documents,
        )

        self.assertIn("nature_pond", context["background_keys"])
        self.assertIn("woven_basket", context["prop_tags"])
        self.assertIn("slow_subtle", context["motion_modifier_tags"])
        self.assertIn("happy", context["emotion_tags"])

    def test_classifies_visual_action_and_builds_stem(self):
        result = classify_fit_vocabulary(
            {
                "word": "다가다",
                "meaning": "대상이 있는 쪽으로 몸을 움직이다",
                "pos_group": "동사",
            }
        )

        self.assertEqual(result["primary_role"], "action")
        self.assertIn("다가", result["match_terms"])
        self.assertIn("walking", result["action_tags"])

    def test_keeps_abstract_noun_non_visual(self):
        result = classify_fit_vocabulary(
            {
                "word": "이유",
                "meaning": "어떤 생각이나 행동을 하게 된 까닭",
                "pos_group": "명사",
            }
        )

        self.assertEqual(result["primary_role"], "non_visual")
        self.assertFalse(result["usable_for_image"])

    def test_matches_inflected_story_word(self):
        document = classify_fit_vocabulary(
            {
                "word": "다가다",
                "meaning": "대상이 있는 쪽으로 몸을 움직이다",
                "pos_group": "동사",
            }
        )
        document.update({"fit_score": 91, "enabled": True})

        context = match_visual_vocabulary(
            "주인공은 빛나는 문으로 천천히 다가갔어요.",
            [document],
        )

        self.assertEqual(context["matched_words"], ["다가다"])
        self.assertIn("walking", context["action_tags"])

    def test_matches_irregular_korean_verb(self):
        document = classify_fit_vocabulary(
            {
                "word": "걷다",
                "meaning": "다리를 움직여 앞으로 가다",
                "pos_group": "동사",
            }
        )
        document.update({"fit_score": 90, "enabled": True})

        context = match_visual_vocabulary(
            "아이는 달빛이 비치는 숲길을 천천히 걸었어요.",
            [document],
        )

        self.assertEqual(context["matched_words"], ["걷다"])
        self.assertIn("walking", context["action_tags"])

    def test_jump_verb_produces_single_whole_body_action(self):
        result = classify_fit_vocabulary(
            {
                "word": "\ub6f0\uc5b4\uc624\ub974\ub2e4",
                "meaning": "\ubab8\uc744 \uc704\ub85c \uc62c\ub824 \ub3c4\uc57d\ud558\ub2e4",
                "pos_group": "verb",
            }
        )

        self.assertIn("jumping", result["action_tags"])
        self.assertEqual(result["action_semantics"]["animation_action"], "jump")
        self.assertEqual(result["action_semantics"]["body_focus"], "whole_body")

    def test_waving_maps_to_wave_animation(self):
        result = classify_fit_vocabulary(
            {
                "word": "\uc190\uc744 \ud754\ub4e4\ub2e4",
                "meaning": "\uc190\uc744 \ud754\ub4e4\uc5b4 \uc778\uc0ac\ud558\ub2e4",
                "pos_group": "verb",
            }
        )

        self.assertIn("waving", result["action_tags"])
        self.assertEqual(result["action_semantics"]["animation_action"], "wave")


if __name__ == "__main__":
    unittest.main()
