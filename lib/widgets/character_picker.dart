import 'package:flutter/material.dart';

import '../main.dart';
import '../models/character_profile.dart';
import '../services/db_service.dart';

class CharacterPicker extends StatefulWidget {
  final String? selectedCharacterKey;
  final ValueChanged<CharacterProfile> onSelected;
  final List<CharacterProfile>? profiles;
  final bool loadRemoteProfiles;

  const CharacterPicker({
    super.key,
    required this.selectedCharacterKey,
    required this.onSelected,
    this.profiles,
    this.loadRemoteProfiles = true,
  });

  @override
  State<CharacterPicker> createState() => _CharacterPickerState();
}

class _CharacterPickerState extends State<CharacterPicker> {
  late List<CharacterProfile> _profiles;
  String _gender = 'male';

  @override
  void initState() {
    super.initState();
    _profiles = widget.profiles ?? CharacterProfileCatalog.defaults;
    _syncGenderWithSelection();
    if (widget.profiles == null && widget.loadRemoteProfiles) {
      _loadRemoteProfiles();
    }
  }

  @override
  void didUpdateWidget(covariant CharacterPicker oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.selectedCharacterKey != widget.selectedCharacterKey) {
      _syncGenderWithSelection();
    }
  }

  Future<void> _loadRemoteProfiles() async {
    try {
      final remoteProfiles = await DbService.fetchCharacterProfiles();
      if (!mounted || remoteProfiles.isEmpty) return;
      setState(() {
        _profiles = CharacterProfileCatalog.mergeRemoteProfiles(remoteProfiles);
        _syncGenderWithSelection();
      });
    } catch (_) {
      // The bundled catalog keeps character selection available offline.
    }
  }

  void _syncGenderWithSelection() {
    final selectedKey = widget.selectedCharacterKey;
    if (selectedKey == null || selectedKey.isEmpty) return;
    final selected = _profiles.where(
      (profile) => profile.characterKey == selectedKey,
    );
    if (selected.isEmpty) return;
    final gender = selected.first.gender;
    if (gender == 'male' || gender == 'female') {
      _gender = gender;
    }
  }

  @override
  Widget build(BuildContext context) {
    final visibleProfiles = _profiles
        .where((profile) => profile.gender == _gender)
        .toList(growable: false);
    final count = visibleProfiles.length;
    final screenHeight = MediaQuery.sizeOf(context).height;
    final shelfHeight = (screenHeight * 0.17).clamp(112.0, 144.0).toDouble();
    final avatarSize = (shelfHeight * 0.62).clamp(68.0, 88.0).toDouble();
    final itemWidth = avatarSize + 24.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SegmentedButton<String>(
          showSelectedIcon: false,
          segments: const [
            ButtonSegment(value: 'male', label: Text('남자', softWrap: false)),
            ButtonSegment(value: 'female', label: Text('여자', softWrap: false)),
          ],
          selected: {_gender},
          onSelectionChanged: (selected) {
            if (selected.isEmpty) return;
            setState(() => _gender = selected.first);
          },
          style: ButtonStyle(
            foregroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.selected)
                  ? Colors.white
                  : AppColors.p300,
            ),
            backgroundColor: WidgetStateProperty.resolveWith(
              (states) => states.contains(WidgetState.selected)
                  ? AppColors.p600
                  : AppColors.card,
            ),
            side: const WidgetStatePropertyAll(
              BorderSide(color: AppColors.border),
            ),
            minimumSize: const WidgetStatePropertyAll(Size(100, 44)),
          ),
        ),
        const SizedBox(height: 12),
        Semantics(
          label: '$_gender character profiles, $count available',
          child: SizedBox(
            height: shelfHeight,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 4),
              itemCount: visibleProfiles.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (context, index) {
                final profile = visibleProfiles[index];
                return SizedBox(
                  width: itemWidth,
                  child: _CharacterProfileCard(
                    key: Key('character-card-${profile.characterKey}'),
                    profile: profile,
                    selected:
                        profile.characterKey == widget.selectedCharacterKey,
                    avatarSize: avatarSize,
                    onTap: () => widget.onSelected(profile),
                  ),
                );
              },
            ),
          ),
        ),
      ],
    );
  }
}

class _CharacterProfileCard extends StatelessWidget {
  final CharacterProfile profile;
  final bool selected;
  final double avatarSize;
  final VoidCallback onTap;

  const _CharacterProfileCard({
    super.key,
    required this.profile,
    required this.selected,
    required this.avatarSize,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final borderColor = selected ? AppColors.teal : AppColors.border;
    return Semantics(
      button: true,
      selected: selected,
      label: profile.displayName,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          hoverColor: Colors.transparent,
          focusColor: Colors.transparent,
          highlightColor: Colors.transparent,
          splashColor: Colors.transparent,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Center(
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Container(
                      width: avatarSize,
                      height: avatarSize,
                      padding: const EdgeInsets.all(2),
                      decoration: BoxDecoration(
                        color: AppColors.card,
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: borderColor,
                          width: selected ? 3 : 1,
                        ),
                      ),
                      child: ClipOval(
                        child: Transform.scale(
                          scale: 2.0,
                          alignment: Alignment.topCenter,
                          child: _ProfileImage(profile: profile),
                        ),
                      ),
                    ),
                    if (selected)
                      const Positioned(
                        top: -4,
                        right: -4,
                        child: Icon(
                          Icons.check_circle_rounded,
                          color: AppColors.teal,
                          size: 20,
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Text(
                profile.displayName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProfileImage extends StatelessWidget {
  final CharacterProfile profile;

  const _ProfileImage({required this.profile});

  @override
  Widget build(BuildContext context) {
    final localAsset = profile.localImageAsset;
    if (localAsset != null) {
      return Image.asset(
        localAsset,
        fit: BoxFit.cover,
        alignment: Alignment.topCenter,
        errorBuilder: (_, _, _) => _placeholder(),
      );
    }

    final imageUrl = DbService.resolveMediaUrl(profile.imageUrl);
    if (imageUrl != null) {
      return Image.network(
        imageUrl,
        headers: DbService.mediaHeaders,
        fit: BoxFit.cover,
        alignment: Alignment.topCenter,
        errorBuilder: (_, _, _) => _placeholder(),
      );
    }
    return _placeholder();
  }

  Widget _placeholder() => const ColoredBox(
    color: AppColors.bg2,
    child: Center(
      child: Icon(Icons.person_rounded, color: AppColors.p300, size: 42),
    ),
  );
}
