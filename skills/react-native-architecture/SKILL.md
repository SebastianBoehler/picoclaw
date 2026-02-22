---
name: react-native-architecture
description: Build production React Native apps with Expo, navigation, native modules, offline sync, and cross-platform patterns. Use when developing mobile apps, implementing native integrations, or architecting React Native projects.
---

# React Native Architecture

Production-ready patterns for React Native development with Expo.

## When to Use
- Starting a new React Native or Expo project
- Implementing complex navigation patterns
- Integrating native modules and platform APIs
- Building offline-first mobile applications
- Optimizing React Native performance
- Setting up CI/CD for mobile releases

## Quick Start
```bash
npx create-expo-app@latest my-app -t expo-template-blank-typescript
npx expo install expo-router react-native-safe-area-context expo-secure-store expo-haptics
```

## Project Structure
```
src/
├── app/          # Expo Router screens ((auth)/, (tabs)/, _layout.tsx)
├── components/   # ui/ + features/
├── hooks/        # Custom hooks
├── services/     # API and native services
├── stores/       # State management
└── types/        # TypeScript types
```

## Key Patterns

### Expo Router Navigation
```tsx
import { Tabs } from 'expo-router'
import { router } from 'expo-router'

router.push('/profile/123')
router.replace('/login')
router.push({ pathname: '/product/[id]', params: { id: '123' } })
```

### Auth Flow
```tsx
// Protect routes based on auth state
const segments = useSegments()
useEffect(() => {
  const inAuthGroup = segments[0] === '(auth)'
  if (!user && !inAuthGroup) router.replace('/login')
  else if (user && inAuthGroup) router.replace('/(tabs)')
}, [user, segments])
```

### Offline-First with React Query
```tsx
import { onlineManager } from '@tanstack/react-query'
import NetInfo from '@react-native-community/netinfo'

onlineManager.setEventListener((setOnline) =>
  NetInfo.addEventListener((state) => setOnline(!!state.isConnected))
)
// Use PersistQueryClientProvider + AsyncStorage persister for offline cache
```

### Native Modules
```tsx
import * as Haptics from 'expo-haptics'
import { Platform } from 'react-native'

// Always guard with Platform.OS check
if (Platform.OS !== 'web') Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)
```

### Performance
```tsx
import { FlashList } from '@shopify/flash-list'  // Use over FlatList
import { memo, useCallback } from 'react'

const Item = memo(({ item, onPress }) => { ... })
// Always memoize renderItem and keyExtractor
```

### Platform-Specific Styles
```tsx
const styles = StyleSheet.create({
  shadow: Platform.select({
    ios: { shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.1 },
    android: { elevation: 4 },
  }),
})
// Or use platform-specific files: Button.ios.tsx, Button.android.tsx
```

## EAS Build & Submit
```bash
eas build --platform all --profile production
eas submit --platform ios
eas submit --platform android
eas update --branch production --message "Bug fixes"
```

## Best Practices
- **Do:** Use Expo, FlashList, Reanimated, StyleSheet.create, test on real devices
- **Don't:** Inline styles, fetch in render, ignore platform differences, store secrets in code, skip error boundaries
