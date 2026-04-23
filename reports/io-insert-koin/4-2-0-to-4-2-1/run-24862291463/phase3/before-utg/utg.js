var utg = 
{
  "nodes": [
    {
      "id": "052812ac517ede05d7cb4f98a078dbb4",
      "shape": "image",
      "image": "states/screen_2026-04-23_224132.png",
      "label": "QuickstepLauncher\n<FIRST>",
      "package": "com.android.launcher3",
      "activity": ".uioverrides.QuickstepLauncher",
      "state_str": "052812ac517ede05d7cb4f98a078dbb4",
      "structure_str": "576c81d4a5f370c48628804efc01be95",
      "title": "<table class=\"table\">\n<tr><th>package</th><td>com.android.launcher3</td></tr>\n<tr><th>activity</th><td>.uioverrides.QuickstepLauncher</td></tr>\n<tr><th>state_str</th><td>052812ac517ede05d7cb4f98a078dbb4</td></tr>\n<tr><th>structure_str</th><td>576c81d4a5f370c48628804efc01be95</td></tr>\n</table>",
      "content": "com.android.launcher3\n.uioverrides.QuickstepLauncher\n052812ac517ede05d7cb4f98a078dbb4\ncom.android.launcher3:id/qsb_widget,com.android.launcher3:id/scrim_view,com.android.quicksearchbox:id/search_plate,com.android.launcher3:id/apps_view,com.android.quicksearchbox:id/search_widget_text,com.android.launcher3:id/page_indicator,com.android.launcher3:id/all_apps_header,com.android.launcher3:id/workspace,com.android.launcher3:id/fast_scroller_popup,android:id/content,com.android.launcher3:id/search_container_workspace,com.android.quicksearchbox:id/search_icon,com.android.launcher3:id/hotseat,com.android.launcher3:id/drag_layer,com.android.launcher3:id/launcher\nPhone,Camera,WebView Browser Tester,Gallery,Messaging",
      "font": "14px Arial red"
    },
    {
      "id": "b4568daed2e04a8085dec1876af2bf73",
      "shape": "image",
      "image": "states/screen_2026-04-23_224134.png",
      "label": "MainActivity",
      "package": "co.touchlab.kampkit",
      "activity": ".android.MainActivity",
      "state_str": "b4568daed2e04a8085dec1876af2bf73",
      "structure_str": "5706af043fc043d96ff62708827d9905",
      "title": "<table class=\"table\">\n<tr><th>package</th><td>co.touchlab.kampkit</td></tr>\n<tr><th>activity</th><td>.android.MainActivity</td></tr>\n<tr><th>state_str</th><td>b4568daed2e04a8085dec1876af2bf73</td></tr>\n<tr><th>structure_str</th><td>5706af043fc043d96ff62708827d9905</td></tr>\n</table>",
      "content": "co.touchlab.kampkit\n.android.MainActivity\nb4568daed2e04a8085dec1876af2bf73\nandroid:id/content,android:id/statusBarBackground\n"
    },
    {
      "id": "84c6b42b9b745c70f16d87e5b4d05152",
      "shape": "image",
      "image": "states/screen_2026-04-23_224137.png",
      "label": "MainActivity\n<LAST>",
      "package": "co.touchlab.kampkit",
      "activity": ".android.MainActivity",
      "state_str": "84c6b42b9b745c70f16d87e5b4d05152",
      "structure_str": "134497a899d96081f5e7263c5f6e83cb",
      "title": "<table class=\"table\">\n<tr><th>package</th><td>co.touchlab.kampkit</td></tr>\n<tr><th>activity</th><td>.android.MainActivity</td></tr>\n<tr><th>state_str</th><td>84c6b42b9b745c70f16d87e5b4d05152</td></tr>\n<tr><th>structure_str</th><td>134497a899d96081f5e7263c5f6e83cb</td></tr>\n</table>",
      "content": "co.touchlab.kampkit\n.android.MainActivity\n84c6b42b9b745c70f16d87e5b4d05152\nandroid:id/content,android:id/statusBarBackground\nafrican,bluetick,airedale,bakharwal,borzoi,bouvier,affenpinscher,basenji,beagle,boxer,brabancon,australian,appenzeller,akita",
      "font": "14px Arial red"
    }
  ],
  "edges": [
    {
      "from": "052812ac517ede05d7cb4f98a078dbb4",
      "to": "b4568daed2e04a8085dec1876af2bf73",
      "id": "052812ac517ede05d7cb4f98a078dbb4-->b4568daed2e04a8085dec1876af2bf73",
      "title": "<table class=\"table\">\n<tr><th>1</th><td>IntentEvent(intent='am start co.touchlab.kampkit/co.touchlab.kampkit.android.MainActivity')</td></tr>\n</table>",
      "label": "1",
      "events": [
        {
          "event_str": "IntentEvent(intent='am start co.touchlab.kampkit/co.touchlab.kampkit.android.MainActivity')",
          "event_id": 1,
          "event_type": "intent",
          "view_images": []
        }
      ]
    },
    {
      "from": "b4568daed2e04a8085dec1876af2bf73",
      "to": "84c6b42b9b745c70f16d87e5b4d05152",
      "id": "b4568daed2e04a8085dec1876af2bf73-->84c6b42b9b745c70f16d87e5b4d05152",
      "title": "<table class=\"table\">\n<tr><th>2</th><td>TouchEvent(state=b4568daed2e04a8085dec1876af2bf73, view=e2ba815e231b82f136b4fc8f4e7b4217(MainActivity/ProgressBar-))</td></tr>\n</table>",
      "label": "2",
      "events": [
        {
          "event_str": "TouchEvent(state=b4568daed2e04a8085dec1876af2bf73, view=e2ba815e231b82f136b4fc8f4e7b4217(MainActivity/ProgressBar-))",
          "event_id": 2,
          "event_type": "touch",
          "view_images": [
            "views/view_e2ba815e231b82f136b4fc8f4e7b4217.png"
          ]
        }
      ]
    }
  ],
  "num_nodes": 3,
  "num_edges": 2,
  "num_effective_events": 2,
  "num_reached_activities": 1,
  "test_date": "2026-04-23 22:41:25",
  "time_spent": 12.006434,
  "num_transitions": 2,
  "device_serial": "emulator-5554",
  "device_model_number": "Android SDK built for x86_64",
  "device_sdk_version": 30,
  "app_sha256": "7df54bc9b56ce04496dee7121ccfa922bf9687c90a6d5366200fd17cca49a2d8",
  "app_package": "co.touchlab.kampkit",
  "app_main_activity": "co.touchlab.kampkit.android.MainActivity",
  "app_num_total_activities": 2
}