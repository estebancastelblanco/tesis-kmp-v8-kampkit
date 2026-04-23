# detekt

## Metrics

* 1 number of properties

* 1 number of functions

* 1 number of classes

* 2 number of packages

* 2 number of kt files

## Complexity Report

* 39 lines of code (loc)

* 31 source lines of code (sloc)

* 13 logical lines of code (lloc)

* 0 comment lines of code (cloc)

* 1 cyclomatic complexity (mcc)

* 0 cognitive complexity

* 1 number of total code smells

* 0% comment source ratio

* 76 mcc per 1,000 lloc

* 76 code smells per 1,000 lloc

## Findings (1)

### style, UnnecessaryAbstractClass (1)

An abstract class is unnecessary. May be refactored to an interface or to a concrete class.

[Documentation](https://detekt.dev/docs/rules/style#unnecessaryabstractclass)

* /tmp/output/phase1/before/shared/src/androidMain/kotlin/co/touchlab/kampkit/models/ViewModel.kt:5:23
```
An abstract class without an abstract member can be refactored to a concrete class.
```
```kotlin
2 
3 import androidx.lifecycle.ViewModel as AndroidXViewModel
4 
5 actual abstract class ViewModel actual constructor() : AndroidXViewModel() {
!                       ^ error
6     actual override fun onCleared() {
7         super.onCleared()
8     }

```

generated with [detekt version 1.23.7](https://detekt.dev/) on 2026-04-23 20:44:57 UTC
