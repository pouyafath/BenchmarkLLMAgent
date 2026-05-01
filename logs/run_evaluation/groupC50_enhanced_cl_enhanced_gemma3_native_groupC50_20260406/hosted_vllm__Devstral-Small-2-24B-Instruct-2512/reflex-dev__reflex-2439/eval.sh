#!/bin/bash
set -uxo pipefail
source /opt/miniconda3/bin/activate
conda activate testbed
cd /testbed
git config --global --add safe.directory /testbed
cd /testbed
git status
git show
git -c core.fileMode=false diff 84858854ae2bc4a5b3b136e04b65b44fef26ebab
source /opt/miniconda3/bin/activate
conda activate testbed
poetry install --with dev || poetry install
git checkout 84858854ae2bc4a5b3b136e04b65b44fef26ebab tests/test_style.py
git apply -v - <<'EOF_114329324912'
diff --git a/tests/test_style.py b/tests/test_style.py
index bc8faa205cd..41a6c765c62 100644
--- a/tests/test_style.py
+++ b/tests/test_style.py
@@ -6,6 +6,7 @@
 
 import reflex as rx
 from reflex import style
+from reflex.style import Style
 from reflex.vars import Var
 
 test_style = [
@@ -73,50 +74,56 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
     ("kwargs", "style_dict", "expected_get_style"),
     [
         ({}, {}, {"css": None}),
-        ({"color": "hotpink"}, {}, {"css": Var.create({"color": "hotpink"})}),
-        ({}, {"color": "red"}, {"css": Var.create({"color": "red"})}),
+        ({"color": "hotpink"}, {}, {"css": Var.create(Style({"color": "hotpink"}))}),
+        ({}, {"color": "red"}, {"css": Var.create(Style({"color": "red"}))}),
         (
             {"color": "hotpink"},
             {"color": "red"},
-            {"css": Var.create({"color": "hotpink"})},
+            {"css": Var.create(Style({"color": "hotpink"}))},
         ),
         (
             {"_hover": {"color": "hotpink"}},
             {},
-            {"css": Var.create({"&:hover": {"color": "hotpink"}})},
+            {"css": Var.create(Style({"&:hover": {"color": "hotpink"}}))},
         ),
         (
             {},
             {"_hover": {"color": "red"}},
-            {"css": Var.create({"&:hover": {"color": "red"}})},
+            {"css": Var.create(Style({"&:hover": {"color": "red"}}))},
         ),
         (
             {},
             {":hover": {"color": "red"}},
-            {"css": Var.create({"&:hover": {"color": "red"}})},
+            {"css": Var.create(Style({"&:hover": {"color": "red"}}))},
         ),
         (
             {},
             {"::-webkit-scrollbar": {"display": "none"}},
-            {"css": Var.create({"&::-webkit-scrollbar": {"display": "none"}})},
+            {"css": Var.create(Style({"&::-webkit-scrollbar": {"display": "none"}}))},
         ),
         (
             {},
             {"::-moz-progress-bar": {"background_color": "red"}},
-            {"css": Var.create({"&::-moz-progress-bar": {"backgroundColor": "red"}})},
+            {
+                "css": Var.create(
+                    Style({"&::-moz-progress-bar": {"backgroundColor": "red"}})
+                )
+            },
         ),
         (
             {"color": ["#111", "#222", "#333", "#444", "#555"]},
             {},
             {
                 "css": Var.create(
-                    {
-                        "@media screen and (min-width: 0)": {"color": "#111"},
-                        "@media screen and (min-width: 30em)": {"color": "#222"},
-                        "@media screen and (min-width: 48em)": {"color": "#333"},
-                        "@media screen and (min-width: 62em)": {"color": "#444"},
-                        "@media screen and (min-width: 80em)": {"color": "#555"},
-                    }
+                    Style(
+                        {
+                            "@media screen and (min-width: 0)": {"color": "#111"},
+                            "@media screen and (min-width: 30em)": {"color": "#222"},
+                            "@media screen and (min-width: 48em)": {"color": "#333"},
+                            "@media screen and (min-width: 62em)": {"color": "#444"},
+                            "@media screen and (min-width: 80em)": {"color": "#555"},
+                        }
+                    )
                 )
             },
         ),
@@ -128,14 +135,16 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
             {},
             {
                 "css": Var.create(
-                    {
-                        "@media screen and (min-width: 0)": {"color": "#111"},
-                        "@media screen and (min-width: 30em)": {"color": "#222"},
-                        "@media screen and (min-width: 48em)": {"color": "#333"},
-                        "@media screen and (min-width: 62em)": {"color": "#444"},
-                        "@media screen and (min-width: 80em)": {"color": "#555"},
-                        "backgroundColor": "#FFF",
-                    }
+                    Style(
+                        {
+                            "@media screen and (min-width: 0)": {"color": "#111"},
+                            "@media screen and (min-width: 30em)": {"color": "#222"},
+                            "@media screen and (min-width: 48em)": {"color": "#333"},
+                            "@media screen and (min-width: 62em)": {"color": "#444"},
+                            "@media screen and (min-width: 80em)": {"color": "#555"},
+                            "backgroundColor": "#FFF",
+                        }
+                    )
                 )
             },
         ),
@@ -147,28 +156,30 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
             {},
             {
                 "css": Var.create(
-                    {
-                        "@media screen and (min-width: 0)": {
-                            "color": "#111",
-                            "backgroundColor": "#FFF",
-                        },
-                        "@media screen and (min-width: 30em)": {
-                            "color": "#222",
-                            "backgroundColor": "#EEE",
-                        },
-                        "@media screen and (min-width: 48em)": {
-                            "color": "#333",
-                            "backgroundColor": "#DDD",
-                        },
-                        "@media screen and (min-width: 62em)": {
-                            "color": "#444",
-                            "backgroundColor": "#CCC",
-                        },
-                        "@media screen and (min-width: 80em)": {
-                            "color": "#555",
-                            "backgroundColor": "#BBB",
-                        },
-                    }
+                    Style(
+                        {
+                            "@media screen and (min-width: 0)": {
+                                "color": "#111",
+                                "backgroundColor": "#FFF",
+                            },
+                            "@media screen and (min-width: 30em)": {
+                                "color": "#222",
+                                "backgroundColor": "#EEE",
+                            },
+                            "@media screen and (min-width: 48em)": {
+                                "color": "#333",
+                                "backgroundColor": "#DDD",
+                            },
+                            "@media screen and (min-width: 62em)": {
+                                "color": "#444",
+                                "backgroundColor": "#CCC",
+                            },
+                            "@media screen and (min-width: 80em)": {
+                                "color": "#555",
+                                "backgroundColor": "#BBB",
+                            },
+                        }
+                    )
                 )
             },
         ),
@@ -185,15 +196,25 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
             {},
             {
                 "css": Var.create(
-                    {
-                        "&:hover": {
-                            "@media screen and (min-width: 0)": {"color": "#111"},
-                            "@media screen and (min-width: 30em)": {"color": "#222"},
-                            "@media screen and (min-width: 48em)": {"color": "#333"},
-                            "@media screen and (min-width: 62em)": {"color": "#444"},
-                            "@media screen and (min-width: 80em)": {"color": "#555"},
+                    Style(
+                        {
+                            "&:hover": {
+                                "@media screen and (min-width: 0)": {"color": "#111"},
+                                "@media screen and (min-width: 30em)": {
+                                    "color": "#222"
+                                },
+                                "@media screen and (min-width: 48em)": {
+                                    "color": "#333"
+                                },
+                                "@media screen and (min-width: 62em)": {
+                                    "color": "#444"
+                                },
+                                "@media screen and (min-width: 80em)": {
+                                    "color": "#555"
+                                },
+                            }
                         }
-                    }
+                    )
                 )
             },
         ),
@@ -202,15 +223,25 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
             {},
             {
                 "css": Var.create(
-                    {
-                        "&:hover": {
-                            "@media screen and (min-width: 0)": {"color": "#111"},
-                            "@media screen and (min-width: 30em)": {"color": "#222"},
-                            "@media screen and (min-width: 48em)": {"color": "#333"},
-                            "@media screen and (min-width: 62em)": {"color": "#444"},
-                            "@media screen and (min-width: 80em)": {"color": "#555"},
+                    Style(
+                        {
+                            "&:hover": {
+                                "@media screen and (min-width: 0)": {"color": "#111"},
+                                "@media screen and (min-width: 30em)": {
+                                    "color": "#222"
+                                },
+                                "@media screen and (min-width: 48em)": {
+                                    "color": "#333"
+                                },
+                                "@media screen and (min-width: 62em)": {
+                                    "color": "#444"
+                                },
+                                "@media screen and (min-width: 80em)": {
+                                    "color": "#555"
+                                },
+                            }
                         }
-                    }
+                    )
                 )
             },
         ),
@@ -224,30 +255,32 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
             {},
             {
                 "css": Var.create(
-                    {
-                        "&:hover": {
-                            "@media screen and (min-width: 0)": {
-                                "color": "#111",
-                                "backgroundColor": "#FFF",
-                            },
-                            "@media screen and (min-width: 30em)": {
-                                "color": "#222",
-                                "backgroundColor": "#EEE",
-                            },
-                            "@media screen and (min-width: 48em)": {
-                                "color": "#333",
-                                "backgroundColor": "#DDD",
-                            },
-                            "@media screen and (min-width: 62em)": {
-                                "color": "#444",
-                                "backgroundColor": "#CCC",
-                            },
-                            "@media screen and (min-width: 80em)": {
-                                "color": "#555",
-                                "backgroundColor": "#BBB",
-                            },
+                    Style(
+                        {
+                            "&:hover": {
+                                "@media screen and (min-width: 0)": {
+                                    "color": "#111",
+                                    "backgroundColor": "#FFF",
+                                },
+                                "@media screen and (min-width: 30em)": {
+                                    "color": "#222",
+                                    "backgroundColor": "#EEE",
+                                },
+                                "@media screen and (min-width: 48em)": {
+                                    "color": "#333",
+                                    "backgroundColor": "#DDD",
+                                },
+                                "@media screen and (min-width: 62em)": {
+                                    "color": "#444",
+                                    "backgroundColor": "#CCC",
+                                },
+                                "@media screen and (min-width: 80em)": {
+                                    "color": "#555",
+                                    "backgroundColor": "#BBB",
+                                },
+                            }
                         }
-                    }
+                    )
                 )
             },
         ),
@@ -261,16 +294,26 @@ def compare_dict_of_var(d1: dict[str, Any], d2: dict[str, Any]):
             {},
             {
                 "css": Var.create(
-                    {
-                        "&:hover": {
-                            "@media screen and (min-width: 0)": {"color": "#111"},
-                            "@media screen and (min-width: 30em)": {"color": "#222"},
-                            "@media screen and (min-width: 48em)": {"color": "#333"},
-                            "@media screen and (min-width: 62em)": {"color": "#444"},
-                            "@media screen and (min-width: 80em)": {"color": "#555"},
-                            "backgroundColor": "#FFF",
+                    Style(
+                        {
+                            "&:hover": {
+                                "@media screen and (min-width: 0)": {"color": "#111"},
+                                "@media screen and (min-width: 30em)": {
+                                    "color": "#222"
+                                },
+                                "@media screen and (min-width: 48em)": {
+                                    "color": "#333"
+                                },
+                                "@media screen and (min-width: 62em)": {
+                                    "color": "#444"
+                                },
+                                "@media screen and (min-width: 80em)": {
+                                    "color": "#555"
+                                },
+                                "backgroundColor": "#FFF",
+                            }
                         }
-                    }
+                    )
                 )
             },
         ),
@@ -304,20 +347,26 @@ class StyleState(rx.State):
     [
         (
             {"color": StyleState.color},
-            {"css": Var.create({"color": StyleState.color})},
+            {"css": Var.create(Style({"color": StyleState.color}))},
         ),
         (
             {"color": f"dark{StyleState.color}"},
-            {"css": Var.create_safe(f'{{"color": `dark{StyleState.color}`}}').to(dict)},
+            {
+                "css": Var.create_safe(f'{{"color": `dark{StyleState.color}`}}').to(
+                    Style
+                )
+            },
         ),
         (
             {"color": StyleState.color, "_hover": {"color": StyleState.color2}},
             {
                 "css": Var.create(
-                    {
-                        "color": StyleState.color,
-                        "&:hover": {"color": StyleState.color2},
-                    }
+                    Style(
+                        {
+                            "color": StyleState.color,
+                            "&:hover": {"color": StyleState.color2},
+                        }
+                    )
                 )
             },
         ),
@@ -325,15 +374,19 @@ class StyleState(rx.State):
             {"color": [StyleState.color, "gray", StyleState.color2, "yellow", "blue"]},
             {
                 "css": Var.create(
-                    {
-                        "@media screen and (min-width: 0)": {"color": StyleState.color},
-                        "@media screen and (min-width: 30em)": {"color": "gray"},
-                        "@media screen and (min-width: 48em)": {
-                            "color": StyleState.color2
-                        },
-                        "@media screen and (min-width: 62em)": {"color": "yellow"},
-                        "@media screen and (min-width: 80em)": {"color": "blue"},
-                    }
+                    Style(
+                        {
+                            "@media screen and (min-width: 0)": {
+                                "color": StyleState.color
+                            },
+                            "@media screen and (min-width: 30em)": {"color": "gray"},
+                            "@media screen and (min-width: 48em)": {
+                                "color": StyleState.color2
+                            },
+                            "@media screen and (min-width: 62em)": {"color": "yellow"},
+                            "@media screen and (min-width: 80em)": {"color": "blue"},
+                        }
+                    )
                 )
             },
         ),
@@ -349,19 +402,27 @@ class StyleState(rx.State):
             },
             {
                 "css": Var.create(
-                    {
-                        "&:hover": {
-                            "@media screen and (min-width: 0)": {
-                                "color": StyleState.color
-                            },
-                            "@media screen and (min-width: 30em)": {
-                                "color": StyleState.color2
-                            },
-                            "@media screen and (min-width: 48em)": {"color": "#333"},
-                            "@media screen and (min-width: 62em)": {"color": "#444"},
-                            "@media screen and (min-width: 80em)": {"color": "#555"},
+                    Style(
+                        {
+                            "&:hover": {
+                                "@media screen and (min-width: 0)": {
+                                    "color": StyleState.color
+                                },
+                                "@media screen and (min-width: 30em)": {
+                                    "color": StyleState.color2
+                                },
+                                "@media screen and (min-width: 48em)": {
+                                    "color": "#333"
+                                },
+                                "@media screen and (min-width: 62em)": {
+                                    "color": "#444"
+                                },
+                                "@media screen and (min-width: 80em)": {
+                                    "color": "#555"
+                                },
+                            }
                         }
-                    }
+                    )
                 )
             },
         ),
@@ -379,19 +440,27 @@ class StyleState(rx.State):
             },
             {
                 "css": Var.create(
-                    {
-                        "&:hover": {
-                            "@media screen and (min-width: 0)": {
-                                "color": StyleState.color
-                            },
-                            "@media screen and (min-width: 30em)": {
-                                "color": StyleState.color2
-                            },
-                            "@media screen and (min-width: 48em)": {"color": "#333"},
-                            "@media screen and (min-width: 62em)": {"color": "#444"},
-                            "@media screen and (min-width: 80em)": {"color": "#555"},
+                    Style(
+                        {
+                            "&:hover": {
+                                "@media screen and (min-width: 0)": {
+                                    "color": StyleState.color
+                                },
+                                "@media screen and (min-width: 30em)": {
+                                    "color": StyleState.color2
+                                },
+                                "@media screen and (min-width: 48em)": {
+                                    "color": "#333"
+                                },
+                                "@media screen and (min-width: 62em)": {
+                                    "color": "#444"
+                                },
+                                "@media screen and (min-width: 80em)": {
+                                    "color": "#555"
+                                },
+                            }
                         }
-                    }
+                    )
                 )
             },
         ),
@@ -410,9 +479,5 @@ def test_style_via_component_with_state(
     comp = rx.el.div(**kwargs)
 
     assert comp.style._var_data == expected_get_style["css"]._var_data
-    # Remove the _var_data from the expected style, since the emotion-formatted
-    # style dict won't actually have it.
-    expected_get_style["css"]._var_data = None
-
     # Assert that style values are equal.
     compare_dict_of_var(comp._get_style(), expected_get_style)

EOF_114329324912
: '>>>>> Start Test Output'
poetry run pytest -rA tests tests/test_style.py
: '>>>>> End Test Output'
git checkout 84858854ae2bc4a5b3b136e04b65b44fef26ebab tests/test_style.py
