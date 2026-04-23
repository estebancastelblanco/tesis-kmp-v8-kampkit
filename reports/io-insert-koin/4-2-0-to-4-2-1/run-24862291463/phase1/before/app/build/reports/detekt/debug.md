# detekt

## Metrics

* 17 number of properties

* 15 number of functions

* 2 number of classes

* 3 number of packages

* 7 number of kt files

## Complexity Report

* 381 lines of code (loc)

* 312 source lines of code (sloc)

* 187 logical lines of code (lloc)

* 23 comment lines of code (cloc)

* 21 cyclomatic complexity (mcc)

* 8 cognitive complexity

* 18 number of total code smells

* 7% comment source ratio

* 112 mcc per 1,000 lloc

* 96 code smells per 1,000 lloc

## Findings (18)

### complexity, TooManyFunctions (1)

Too many functions inside a/an file/class/object/interface always indicate a violation of the single responsibility principle. Maybe the file/class/object/interface wants to manage too many things at once. Extract functionality which clearly belongs together.

[Documentation](https://detekt.dev/docs/rules/complexity#toomanyfunctions)

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:1:1
```
File '/tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt' with '12' functions detected. Defined threshold inside files is set to '11'
```
```kotlin
1 package co.touchlab.kampkit.android.ui
! ^ error
2 
3 import androidx.compose.animation.Crossfade
4 import androidx.compose.animation.core.FastOutSlowInEasing

```

### naming, FunctionNaming (13)

Function names should follow the naming convention set in the configuration.

[Documentation](https://detekt.dev/docs/rules/naming#functionnaming)

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:45:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
42 import kotlinx.coroutines.launch
43 
44 @Composable
45 fun MainScreen(viewModel: BreedViewModel, log: Logger) {
!!     ^ error
46     val dogsState by viewModel.breedState.collectAsStateWithLifecycle()
47     val scope = rememberCoroutineScope()
48 

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:64:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
61 
62 @OptIn(ExperimentalMaterialApi::class)
63 @Composable
64 fun MainScreenContent(
!!     ^ error
65     dogsState: BreedViewState,
66     onRefresh: () -> Unit = {},
67     onSuccess: (List<Breed>) -> Unit = {},

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:107:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
104 }
105 
106 @Composable
107 fun Empty() {
!!!     ^ error
108     Column(
109         modifier = Modifier
110             .fillMaxSize()

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:120:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
117 }
118 
119 @Composable
120 fun Error(error: String) {
!!!     ^ error
121     Column(
122         modifier = Modifier
123             .fillMaxSize()

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:133:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
130 }
131 
132 @Composable
133 fun Success(successData: List<Breed>, favoriteBreed: (Breed) -> Unit) {
!!!     ^ error
134     DogList(breeds = successData, favoriteBreed)
135 }
136 

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:138:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
135 }
136 
137 @Composable
138 fun DogList(breeds: List<Breed>, onItemClick: (Breed) -> Unit) {
!!!     ^ error
139     LazyColumn {
140         items(breeds) { breed ->
141             DogRow(breed) {

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:150:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
147 }
148 
149 @Composable
150 fun DogRow(breed: Breed, onClick: (Breed) -> Unit) {
!!!     ^ error
151     Row(
152         Modifier
153             .clickable { onClick(breed) }

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:162:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
159 }
160 
161 @Composable
162 fun FavoriteIcon(breed: Breed) {
!!!     ^ error
163     Crossfade(
164         targetState = !breed.favorite,
165         animationSpec = TweenSpec(

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:187:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
184 
185 @Preview
186 @Composable
187 fun MainScreenContentPreview_Success() {
!!!     ^ error
188     MainScreenContent(
189         dogsState = BreedViewState.Content(
190             breeds = listOf(

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:200:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
197 
198 @Preview
199 @Composable
200 fun MainScreenContentPreview_Initial() {
!!!     ^ error
201     MainScreenContent(dogsState = BreedViewState.Initial)
202 }
203 

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:206:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
203 
204 @Preview
205 @Composable
206 fun MainScreenContentPreview_Empty() {
!!!     ^ error
207     MainScreenContent(dogsState = BreedViewState.Empty())
208 }
209 

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/Composables.kt:212:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
209 
210 @Preview
211 @Composable
212 fun MainScreenContentPreview_Error() {
!!!     ^ error
213     MainScreenContent(dogsState = BreedViewState.Error("Something went wrong!"))
214 }
215 

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/theme/Theme.kt:31:5
```
Function names should match the pattern: [a-z][a-zA-Z0-9]*
```
```kotlin
28 )
29 
30 @Composable
31 fun KaMPKitTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
!!     ^ error
32     val colors = if (darkTheme) {
33         DarkColorPalette
34     } else {

```

### style, MagicNumber (4)

Report magic numbers. Magic number is a numeric literal that is not defined as a constant and hence it's unclear what the purpose of this number is. It's better to declare such numbers as constants and give them a proper name. By default, -1, 0, 1, and 2 are not considered to be magic numbers.

[Documentation](https://detekt.dev/docs/rules/style#magicnumber)

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/theme/Color.kt:5:23
```
This expression contains a magic number. Consider defining it to a well named constant.
```
```kotlin
2 
3 import androidx.compose.ui.graphics.Color
4 
5 val Purple200 = Color(0xFFBB86FC)
!                       ^ error
6 val Purple500 = Color(0xFF6200EE)
7 val Purple700 = Color(0xFF3700B3)
8 val Teal200 = Color(0xFF03DAC5)

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/theme/Color.kt:6:23
```
This expression contains a magic number. Consider defining it to a well named constant.
```
```kotlin
3  import androidx.compose.ui.graphics.Color
4  
5  val Purple200 = Color(0xFFBB86FC)
6  val Purple500 = Color(0xFF6200EE)
!                        ^ error
7  val Purple700 = Color(0xFF3700B3)
8  val Teal200 = Color(0xFF03DAC5)
9  

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/theme/Color.kt:7:23
```
This expression contains a magic number. Consider defining it to a well named constant.
```
```kotlin
4  
5  val Purple200 = Color(0xFFBB86FC)
6  val Purple500 = Color(0xFF6200EE)
7  val Purple700 = Color(0xFF3700B3)
!                        ^ error
8  val Teal200 = Color(0xFF03DAC5)
9  

```

* /tmp/output/phase1/before/app/src/main/kotlin/co/touchlab/kampkit/android/ui/theme/Color.kt:8:21
```
This expression contains a magic number. Consider defining it to a well named constant.
```
```kotlin
5  val Purple200 = Color(0xFFBB86FC)
6  val Purple500 = Color(0xFF6200EE)
7  val Purple700 = Color(0xFF3700B3)
8  val Teal200 = Color(0xFF03DAC5)
!                      ^ error
9  

```

generated with [detekt version 1.23.7](https://detekt.dev/) on 2026-04-23 22:40:17 UTC
