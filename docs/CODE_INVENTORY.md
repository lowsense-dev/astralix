# Реестр кода astralix

Структурная инвентаризация AST. Наличие файла в этой таблице не означает исчерпывающую ручную проверку каждой его строки.

| Файл | Строк | Классы / функции верхнего уровня |
|---|---:|---|
| [astralix/__init__.py](../astralix/__init__.py) | 24 |  |
| [astralix/__main__.py](../astralix/__main__.py) | 142 | `get_data_root`, `wipe_data` |
| [astralix/_backup.py](../astralix/_backup.py) | 48 | `read_entry`, `module_plan` |
| [astralix/_branding.py](../astralix/_branding.py) | 6 |  |
| [astralix/_dependencies.py](../astralix/_dependencies.py) | 46 | `dependency_installation`, `install_command` |
| [astralix/_event_filters.py](../astralix/_event_filters.py) | 122 | `find_failed_tag` |
| [astralix/_internal.py](../astralix/_internal.py) | 461 | `register_secret`, `register_secrets`, `redact`, `RedactingFormatter`, `PrivateRotatingFileHandler`, `private_write`, `validate_url`, `auth_for_url`, `fetch_text`, `get_client_id`, `set_client_id`, `resolve_client_id`, `client_id_override`, `client_id_scope`, `tag_client_id`, `_track_task`, `install_task_tracking`, `fw_protect`, `get_startup_callback`, `die`, `restart`, `print_banner`, `check_commit_ancestor`, `get_branch_name`, `reset_to_master`, `restore_worktree` |
| [astralix/_local_storage.py](../astralix/_local_storage.py) | 180 | `LocalStorage`, `RemoteStorage` |
| [astralix/_login.py](../astralix/_login.py) | 60 | `login_step`, `LoginSessions` |
| [astralix/_reference_finder.py](../astralix/_reference_finder.py) | 130 | `proxy0`, `replace_all_refs` |
| [astralix/_types.py](../astralix/_types.py) | 3 |  |
| [astralix/configurator.py](../astralix/configurator.py) | 88 | `tty_print`, `tty_input`, `api_config` |
| [astralix/database.py](../astralix/database.py) | 478 | `NoAssetsChannel`, `NoContentChannel`, `Database` |
| [astralix/dispatcher.py](../astralix/dispatcher.py) | 675 | `_decrement_ratelimit`, `CommandDispatcher` |
| [astralix/inline/bot_pm.py](../astralix/inline/bot_pm.py) | 86 | `BotPM` |
| [astralix/inline/core.py](../astralix/inline/core.py) | 557 | `InlineManager` |
| [astralix/inline/events.py](../astralix/inline/events.py) | 487 | `Events` |
| [astralix/inline/form.py](../astralix/inline/form.py) | 617 | `Placeholder`, `Form` |
| [astralix/inline/gallery.py](../astralix/inline/gallery.py) | 740 | `ListGalleryHelper`, `Gallery` |
| [astralix/inline/list.py](../astralix/inline/list.py) | 353 | `List` |
| [astralix/inline/query_gallery.py](../astralix/inline/query_gallery.py) | 152 | `QueryGallery` |
| [astralix/inline/tl.py](../astralix/inline/tl.py) | 562 | `TelethonBot`, `web_document`, `make_button` |
| [astralix/inline/token_obtainment.py](../astralix/inline/token_obtainment.py) | 385 | `TokenObtainment` |
| [astralix/inline/types.py](../astralix/inline/types.py) | 466 | `InlineMessage`, `_User`, `_Chat`, `_MessageProxy`, `BotInlineMessage`, `_CallbackMixin`, `InlineCall`, `BotInlineCall`, `InlineUnit`, `BotMessage`, `InlineQuery` |
| [astralix/inline/utils.py](../astralix/inline/utils.py) | 778 | `Utils` |
| [astralix/loader.py](../astralix/loader.py) | 1481 | `stop_placeholder`, `Placeholder`, `patched_import`, `InfiniteLoop`, `loop`, `_iter_module_files`, `translatable_docstring`, `ratelimit`, `tag`, `_mark_method`, `command`, `debug_method`, `inline_handler`, `watcher`, `callback_handler`, `raw_handler`, `need_update`, `Modules` |
| [astralix/log.py](../astralix/log.py) | 680 | `getlines`, `override_text`, `AstralixException`, `TelegramLogsHandler`, `check_branch`, `init` |
| [astralix/main.py](../astralix/main.py) | 1241 | `generate_app_name`, `get_app_name`, `generate_random_system_version`, `run_config`, `_read_config`, `get_config_key`, `save_config_key`, `parse_arguments`, `SuperList`, `InteractiveAuthRequired`, `raise_auth`, `Astralix` |
| [astralix/modules/api_protection.py](../astralix/modules/api_protection.py) | 275 | `_module_name`, `_current_task_label`, `find_call_chain`, `APIRatelimiterMod` |
| [astralix/modules/astralix_backup.py](../astralix/modules/astralix_backup.py) | 571 | `AstralixBackupMod` |
| [astralix/modules/astralix_config.py](../astralix/modules/astralix_config.py) | 1785 | `_InlineFormDraft`, `AstralixConfigMod` |
| [astralix/modules/astralix_info.py](../astralix/modules/astralix_info.py) | 287 | `AstralixInfoMod` |
| [astralix/modules/astralix_security.py](../astralix/modules/astralix_security.py) | 1400 | `AstralixSecurityMod` |
| [astralix/modules/astralix_settings.py](../astralix/modules/astralix_settings.py) | 526 | `AstralixSettingsMod` |
| [astralix/modules/astralix_web.py](../astralix/modules/astralix_web.py) | 576 | `AstralixWebMod` |
| [astralix/modules/eval.py](../astralix/modules/eval.py) | 524 | `Evaluator` |
| [astralix/modules/help.py](../astralix/modules/help.py) | 580 | `Help` |
| [astralix/modules/inline_stuff.py](../astralix/modules/inline_stuff.py) | 186 | `InlineStuff` |
| [astralix/modules/loader.py](../astralix/modules/loader.py) | 2343 | `FakeOne`, `ModuleInstallError`, `LoaderMod` |
| [astralix/modules/loader_restrictor.py](../astralix/modules/loader_restrictor.py) | 208 | `PollStep`, `PollStatus`, `LoaderRestrictor` |
| [astralix/modules/quickstart.py](../astralix/modules/quickstart.py) | 117 | `Quickstart` |
| [astralix/modules/settings.py](../astralix/modules/settings.py) | 726 | `CoreMod` |
| [astralix/modules/terminal.py](../astralix/modules/terminal.py) | 916 | `hash_msg`, `read_stream`, `sudo_stdin_command`, `MessageEditor`, `SudoMessageEditor`, `RawMessageEditor`, `InlineMessageEditor`, `TerminalMod` |
| [astralix/modules/test.py](../astralix/modules/test.py) | 458 | `TestMod` |
| [astralix/modules/translate.py](../astralix/modules/translate.py) | 150 | `Translator` |
| [astralix/modules/translations.py](../astralix/modules/translations.py) | 294 | `Translations` |
| [astralix/modules/updater.py](../astralix/modules/updater.py) | 906 | `UpdaterMod` |
| [astralix/pointers.py](../astralix/pointers.py) | 495 | `_wrap`, `NestedPointerDict`, `NestedPointerList`, `PointerList`, `PointerDict`, `BaseSerializingMiddlewareDict`, `BaseSerializingMiddlewareList`, `NamedTupleMiddlewareList`, `NamedTupleMiddlewareDict` |
| [astralix/qr.py](../astralix/qr.py) | 1566 | `rs_blocks`, `glog`, `gexp`, `Polynomial`, `RSBlock`, `_data_count`, `BCH_type_info`, `BCH_type_number`, `BCH_digit`, `pattern_position`, `mask_func`, `mode_sizes_for_version`, `length_in_bits`, `check_version`, `lost_point`, `_lost_point_level1`, `_lost_point_level2`, `_lost_point_level3`, `_lost_point_level4`, `optimal_data_chunks`, `_optimal_split`, `to_bytestring`, `optimal_mode`, `QRData`, `BitBuffer`, `create_bytes`, `create_data`, `DataOverflowError`, `_check_box_size`, `_check_border`, `_check_mask_pattern`, `copy_2d_array`, `ActiveWithNeighbors`, `QRCode` |
| [astralix/secure/__init__.py](../astralix/secure/__init__.py) | 1 |  |
| [astralix/secure/customtl.py](../astralix/secure/customtl.py) | 86 | `MTProtoState`, `ConnectionTcpFull` |
| [astralix/secure/patcher.py](../astralix/secure/patcher.py) | 35 | `patch` |
| [astralix/security.py](../astralix/security.py) | 685 | `SecurityGroup`, `owner`, `_deprecated`, `group_owner`, `group_admin_add_admins`, `group_admin_change_info`, `group_admin_ban_users`, `group_admin_delete_messages`, `group_admin_pin_messages`, `group_admin_invite_users`, `group_admin`, `group_member`, `pm`, `unrestricted`, `inline_everyone`, `_sec`, `SecurityManager` |
| [astralix/tl_cache.py](../astralix/tl_cache.py) | 1119 | `AstralixMessagePacker`, `hashable`, `CustomTelegramClient` |
| [astralix/translations.py](../astralix/translations.py) | 372 | `normalize_language`, `normalize_language_token`, `iter_language_codes`, `get_language_pack_path`, `fmt`, `BaseTranslator`, `Translator`, `ExternalTranslator`, `Strings` |
| [astralix/types.py](../astralix/types.py) | 1184 | `StringLoader`, `Module`, `Library`, `LoadError`, `CoreOverwriteError`, `CoreUnloadError`, `SelfUnload`, `SelfSuspend`, `StopLoop`, `ModuleConfig`, `_Placeholder`, `wrap`, `syncwrap`, `ConfigValue`, `ConfigCategory`, `_get_members`, `CacheRecordEntity`, `CacheRecordPerms`, `CacheRecordFullChannel`, `CacheRecordFullUser`, `get_commands`, `get_inline_handlers`, `get_callback_handlers`, `get_watchers` |
| [astralix/utils/__init__.py](../astralix/utils/__init__.py) | 12 |  |
| [astralix/utils/args.py](../astralix/utils/args.py) | 207 | `iter_attrs`, `validate_html`, `get_kwargs`, `get_args`, `get_args_raw`, `get_args_html`, `get_args_split_by`, `get_args_int`, `get_args_bool`, `normalize_prefixes`, `user_prefixes`, `match_prefix`, `format_prefixes` |
| [astralix/utils/astralix.py](../astralix/utils/astralix.py) | 43 | `get_version_raw`, `get_base_dir`, `get_dir` |
| [astralix/utils/entity.py](../astralix/utils/entity.py) | 872 | `get_lang_flag`, `get_entity_url`, `get_link`, `remove_emoji`, `remove_html`, `check_url`, `is_private_asset_channel`, `asset_channel`, `asset_forum_topic`, `wait_for_content_channel`, `get_topic_id`, `set_avatar`, `get_target`, `get_user`, `get_chat_id`, `get_entity_id`, `escape_html`, `escape_non_html`, `escape_quotes`, `relocate_entities`, `find_caller`, `dnd`, `ascii_face` |
| [astralix/utils/git.py](../astralix/utils/git.py) | 136 | `_is_no_git`, `get_git_info`, `get_git_hash`, `get_commit_url`, `get_git_status`, `get_last_commit_message`, `get_commit_count`, `is_up_to_date` |
| [astralix/utils/grep.py](../astralix/utils/grep.py) | 100 | `_RichGrepParser`, `filter_rich_lines` |
| [astralix/utils/messages.py](../astralix/utils/messages.py) | 750 | `get_topic`, `mime_type`, `get_message_link`, `smart_split`, `array_sum`, `_send_rich_message`, `_edit_rich_message`, `_edit_inline_rich_message`, `answer_with_media_fallback`, `answer`, `answer_file`, `censor`, `is_serializable`, `extract_urls`, `has_media` |
| [astralix/utils/network.py](../astralix/utils/network.py) | 69 | `get_hostname`, `resolve_domain`, `is_port_open`, `get_network_interfaces` |
| [astralix/utils/other.py](../astralix/utils/other.py) | 251 | `ensure_child_watcher`, `rand`, `invite_inline_bot`, `run_sync`, `run_async`, `merge`, `chunks`, `atexit`, `_copy_tl`, `format_file_size`, `is_url`, `get_iso_time`, `safe_getattr`, `allowed_ids` |
| [astralix/utils/placeholders.py](../astralix/utils/placeholders.py) | 147 | `LazyPlaceholderData`, `register_placeholder`, `get_placeholder`, `get_placeholders`, `unregister_placeholders`, `config_placeholders`, `module_placeholders`, `help_placeholders`, `debug_placeholders` |
| [astralix/utils/platform.py](../astralix/utils/platform.py) | 269 | `get_named_platform`, `get_named_platform_emoji`, `get_platform_emoji`, `uptime`, `formatted_uptime`, `get_ram_usage`, `get_ram_usage_system`, `get_swap_usage`, `get_cpu_usage`, `get_ip_address`, `get_disk_usage` |
| [astralix/utils/rich.py](../astralix/utils/rich.py) | 323 | `_escape`, `_attribute`, `_text`, `_caption`, `_media`, `_list_item`, `_table_cell`, `_button`, `_block`, `rich_message_to_html`, `install_rich_message_support` |
| [astralix/validators.py](../astralix/validators.py) | 875 | `ValidationError`, `Validator`, `Boolean`, `Integer`, `Choice`, `MultiChoice`, `Series`, `Link`, `String`, `RegExp`, `Float`, `TelegramID`, `Union`, `NoneType`, `Hidden`, `Emoji`, `EntityLike`, `RandomLinkList`, `RandomLink` |
| [astralix/version.py](../astralix/version.py) | 47 | `check_branch` |
