package co.touchlab.kampkit.db

import kotlin.Boolean
import kotlin.Long
import kotlin.String

public data class Breed(
  public val id: Long,
  public val name: String,
  public val favorite: Boolean,
)
